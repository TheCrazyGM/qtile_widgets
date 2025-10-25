"""
Qtile GenPollUrl widget to display SiriusXM-style "now playing" data
by polling a JSON endpoint and formatting the response as "{title} - {artist}",
with an optional verbose mode that prefixes the channel and appends a timestamp.

Expected JSON fields in the response:
  - title: string
  - artist: string
  - channel_id: string (optional)
  - played_at_ms: integer milliseconds since epoch (optional)

Example usage in config.py:

    from now_playing import NowPlaying

    NowPlaying(
        channel="octane",
        verbose=False,
        update_interval=5,
        foreground=colors["foreground"],
        background=colors["background"],
        padding=5,
    )
"""

import asyncio
from typing import Any, Dict, Optional

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientError, ContentTypeError
from libqtile.command.base import expose_command
from libqtile.log_utils import logger
from libqtile.widget.generic_poll_text import GenPollUrl, xmlparse


class NowPlaying(GenPollUrl):
    """Poll an HTTP JSON endpoint for now playing info and render text."""

    defaults = [
        (
            "url",
            "http://localhost:9999/now_playing?channel={channel}",
            "Endpoint returning JSON with title/artist/channel_id/played_at_ms.",
        ),
        (
            "channel",
            "octane",
            "The channel to query for now playing info.",
        ),
        (
            "verbose",
            False,
            "Include channel in output.",
        ),
        (
            "format",
            "{title} - {artist}",
            "Display format when verbose is False.",
        ),
        (
            "verbose_format",
            "[{channel}] {title} - {artist}",
            "Display format when verbose is True.",
        ),
        (
            "error_text",
            "Now Playing: Error",
            "Text to display when parsing fails.",
        ),
        (
            "update_interval",
            5,
            "Seconds between polls.",
        ),
        (
            "max_chars",
            None,
            "If set, truncate output to this many characters (with ellipsis).",
        ),
        (
            "markup",
            False,
            "Whether to parse Pango markup in text (disabled to avoid parse errors).",
        ),
    ]

    def __init__(self, **config: Any) -> None:
        # Force JSON parsing in GenPollUrl so `parse` receives a dict
        config.setdefault("json", True)
        # Disable Pango markup parsing by default; raw text often contains '&', '<', etc.
        config.setdefault("markup", False)
        super().__init__(**config)
        self.add_defaults(NowPlaying.defaults)
        self.url_template = self.url
        self.url = self.url_template.format(channel=self.channel)
        self._session: Optional[ClientSession] = None

    @expose_command()
    def set_channel(self, channel: str) -> str:
        """Change channel and refresh. Returns active channel."""
        self.channel = str(channel)
        self.url = self.url_template.format(channel=self.channel)
        try:
            # Schedule an immediate poll to reflect the change
            self.refresh()
        except Exception as e:
            logger.error(
                "NowPlaying: failed to schedule refresh after channel change: %s", e
            )
        return self.channel

    @expose_command()
    def get_channel(self) -> str:
        """Get current channel."""
        return self.channel

    def refresh(self) -> None:
        """Trigger an immediate poll and update the widget text."""

        def _do_refresh() -> None:
            try:
                text = self.poll()
                self.update(text)
            except Exception as e:
                logger.error("NowPlaying: refresh failed: %s", e)

        # Run on the Qtile event loop to avoid threading issues
        try:
            self.timeout_add(0, _do_refresh)
        except Exception as e:
            logger.error("NowPlaying: failed to schedule refresh: %s", e)

    async def apoll(self) -> str:
        """Custom poll with guards for non-JSON responses and failures."""
        if not self.parse or not self.url:
            return "Invalid config"

        headers = self.headers.copy()
        data = self.data
        method = "POST" if data else "GET"

        try:
            session = await self._get_session()
            async with session.request(
                method=method, url=self.url, data=data, headers=headers
            ) as response:
                if response.status >= 400:
                    logger.warning(
                        "NowPlaying: request to %s returned HTTP %s",
                        self.url,
                        response.status,
                    )
                    return self.error_text

                if self.json:
                    content_type = response.headers.get("Content-Type", "")
                    if "json" not in content_type.lower():
                        logger.warning(
                            "NowPlaying: unexpected content type '%s' from %s",
                            content_type,
                            self.url,
                        )
                        return self.error_text
                    try:
                        body = await response.json()
                    except ContentTypeError as e:
                        logger.warning(
                            "NowPlaying: JSON decoding failed for %s: %s",
                            self.url,
                            e,
                        )
                        return self.error_text
                elif self.xml:
                    text_body = await response.text()
                    body = xmlparse(text_body)
                else:
                    body = await response.text()

            try:
                text = self.parse(body)
            except Exception as e:
                logger.error("NowPlaying: parse error: %s", e)
                return self.error_text
        except (ClientError, asyncio.TimeoutError) as e:
            logger.warning("NowPlaying: request failed for %s: %s", self.url, e)
            return self.error_text
        except Exception:
            logger.exception("NowPlaying: unexpected error polling widget")
            return self.error_text

        return text

    async def _get_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession()
        return self._session

    def finalize(self) -> None:
        session = self._session
        self._session = None

        if session and not session.closed:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.create_task(session.close())
            else:
                asyncio.run(session.close())

        super().finalize()

    def parse(self, body: Dict[str, Any]) -> str:
        """Parse JSON and render formatted output.

        Expected keys: title, artist, optional channel_id, played_at_ms.
        """
        try:
            title = str(body.get("title", "") or "").strip()
            artist = str(body.get("artist", "") or "").strip()
            channel = str(body.get("channel_id", "") or "").strip()
        except Exception as e:  # Defensive: unexpected schema types
            logger.error("NowPlaying: invalid response type: %s", e)
            return self.error_text

        if not title or not artist:
            logger.error("NowPlaying: missing title/artist in response: %s", body)
            return self.error_text

        # Select format based on verbosity
        tpl = self.verbose_format if self.verbose else self.format
        text = tpl.format(
            title=title,
            artist=artist,
            channel=channel,
        )

        # Optional truncation
        if (
            isinstance(self.max_chars, int)
            and self.max_chars > 3
            and len(text) > self.max_chars
        ):
            text = text[: self.max_chars - 1].rstrip() + "…"

        return text
