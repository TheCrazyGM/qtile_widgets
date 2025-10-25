"""Hive notifications widgets for Qtile bars.

Provides a compact summary widget that polls unread Hive notifications and a
companion detail widget for rendering a short list of recent items.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

from libqtile.command.base import expose_command
from libqtile.log_utils import logger
from libqtile.widget.generic_poll_text import GenPollText

from nectar import Hive
from nectar.account import Account
from nectar.nodelist import NodeList
from libqtile.popup import Popup

if TYPE_CHECKING:
    from libqtile.bar import Bar
    from libqtile.core.manager import Qtile


_HIVE_DEFAULT_NODES: Sequence[str] = (
    "https://api.syncad.com",
    "https://api.hive.blog",
)

_NOTIFICATION_TYPE_ICONS: Dict[str, str] = {
    "vote": "👍",
    "mention": "@",
    "reply": "💬",
    "reblog": "🔁",
    "transfer": "💸",
}


def _extract_notification_details(notif: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """Return tuple of (type, sender, date_str, message) for a Hive notification."""

    notif_type = str(notif.get("type") or "").strip()
    date = notif.get("date", "")
    if hasattr(date, "strftime"):
        date_str = date.strftime("%Y-%m-%d %H:%M:%S")
    else:
        date_str = str(date or "")

    sender = ""
    msg = str(notif.get("msg") or "")
    url = str(notif.get("url") or "")

    # Attempt to pull a username from the message first
    if "@" in msg:
        for part in msg.split():
            if part.startswith("@") and len(part) > 1:
                sender = part
                break

    if not sender and url.startswith("@"):
        sender = url.split("/", 1)[0]

    if not sender:
        sender = notif.get("from", "") or "?"

    message = _build_message_for_type(notif_type, msg, url)
    return notif_type, sender, date_str, message


def _build_message_for_type(notif_type: str, msg: str, url: str) -> str:
    """Generate a concise description for the notification."""

    if not msg and url:
        return f"re: {url.split('/', 1)[1] if '/' in url else url}"

    msg = msg.strip()
    if not msg:
        return url or ""

    if notif_type == "vote":
        if "voted on your post" in msg:
            if "($" in msg and ")" in msg:
                amount = msg.split("($")[1].split(")")[0]
                return f"voted {amount} on your post"
            return "voted on your post"
    elif notif_type == "mention":
        if "mentioned you" in msg:
            if "and" in msg and "others" in msg:
                others = msg.split("and ")[1].split(" others")[0]
                return f"mentioned you and {others} others"
            return "mentioned you"
    elif notif_type == "reply":
        if "replied to" in msg:
            return "replied to you"
    elif notif_type == "reblog":
        if "reblogged your post" in msg:
            return "reblogged your post"

    return msg


class HiveNotificationsSummary(GenPollText):
    """Display the number of unread Hive notifications."""

    defaults = [
        ("account", None, "Hive account name to query (required)."),
        (
            "only_unread",
            True,
            "Fetch only unread notifications (recommended).",
        ),
        ("limit", 50, "Maximum number of notifications to fetch (API limit 100)."),
        (
            "nodes",
            list(_HIVE_DEFAULT_NODES),
            "Hive RPC nodes to use for queries.",
        ),
        (
            "format",
            "🔔 {count}",
            "Display format when notifications exist. Variables: {count}.",
        ),
        (
            "empty_text",
            "✓",
            "Text to display when there are no matching notifications.",
        ),
        ("error_text", "Notifications: Error", "Fallback text on failure."),
        (
            "active_wif_env",
            "ACTIVE_WIF",
            "Environment variable containing ACTIVE private key to mark read (optional).",
        ),
        ("popup_enabled", True, "Show popup window with details on click."),
        ("popup_width", 420, "Popup width in pixels."),
        ("popup_height", 260, "Popup height in pixels."),
        ("popup_opacity", 0.95, "Popup window opacity."),
        ("popup_border_width", 1, "Popup border width."),
        ("popup_border_color", "#444444", "Popup border colour."),
        ("popup_foreground", "#F8F8F2", "Popup text colour."),
        ("popup_background", "#282A36", "Popup background colour."),
        ("popup_font", "JetBrainsMono Nerd Font", "Popup font family."),
        ("popup_fontsize", 12, "Popup font size."),
        ("popup_padding", 10, "Popup inner padding."),
    ]

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self.add_defaults(HiveNotificationsSummary.defaults)
        self._hive: Optional[Hive] = None
        self._account: Optional[Account] = None
        self._notifications: List[Dict[str, Any]] = []
        self._last_fetch: float = 0.0
        self._listeners: List["HiveNotificationsList"] = []
        self._popup: Optional[Popup] = None
        self._popup_visible: bool = False

        if not getattr(self, "account", None):
            logger.error("HiveNotificationsSummary: 'account' is required")

    def _configure(self, qtile: Qtile, bar: Bar) -> None:
        super()._configure(qtile, bar)
        # Trigger an eager poll once the widget is live
        self.timeout_add(0, self.force_update)
        self.add_callbacks({"Button1": self.toggle_popup})

    def register_listener(self, listener: "HiveNotificationsList") -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unregister_listener(self, listener: "HiveNotificationsList") -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def poll(self) -> str:
        try:
            notifications = self._fetch_notifications(force=True)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("HiveNotificationsSummary: poll failed: %s", exc)
            return self.error_text

        count = len(notifications)
        text = self.format.format(count=count) if count else self.empty_text
        self._notify_listeners()
        self._update_popup_content(notifications)
        return text

    def _fetch_notifications(self, force: bool = False) -> List[Dict[str, Any]]:
        if not self.account:
            return []

        if (
            not force
            and self._notifications
            and (time.time() - self._last_fetch) < max(float(self.update_interval or 0), 1.0)
        ):
            return self._notifications

        if not self._ensure_client():
            return []

        try:
            notifications = self._account.get_notifications(  # type: ignore[union-attr]
                only_unread=bool(self.only_unread),
                limit=int(self.limit or 50),
            )
        except Exception as exc:
            logger.error("HiveNotificationsSummary: failed to fetch notifications: %s", exc)
            raise

        if not isinstance(notifications, list):
            notifications = list(notifications or [])

        self._notifications = notifications
        self._last_fetch = time.time()
        return self._notifications

    def get_notifications(self, force: bool = False) -> List[Dict[str, Any]]:
        try:
            return list(self._fetch_notifications(force=force))
        except Exception:
            return []

    def _ensure_client(self) -> bool:
        if self._account is not None:
            return True

        try:
            try:
                nodes = NodeList()
                nodes.update_nodes()
                hivex = Hive(node=nodes.get_hive_nodes())
            except Exception:
                hivex = Hive(node=self.nodes)

            account = Account(str(self.account), blockchain_instance=hivex)
        except Exception as exc:
            logger.error("HiveNotificationsSummary: failed to init Hive client: %s", exc)
            self._account = None
            self._hive = None
            return False

        self._hive = hivex
        self._account = account
        return True

    def _notify_listeners(self) -> None:
        for listener in list(self._listeners):
            try:
                listener.refresh_from_summary()
            except Exception as exc:
                logger.debug("HiveNotificationsSummary: listener refresh failed: %s", exc)

    def _ensure_popup(self) -> Optional[Popup]:
        if not self.popup_enabled:
            return None

        if self._popup is None and self.qtile is not None:
            try:
                popup = Popup(
                    self.qtile,
                    width=int(self.popup_width),
                    height=int(self.popup_height),
                    opacity=float(self.popup_opacity),
                    foreground=str(self.popup_foreground),
                    background=str(self.popup_background),
                    border=str(self.popup_border_color),
                    border_width=int(self.popup_border_width),
                    font=str(self.popup_font),
                    fontsize=int(self.popup_fontsize),
                    horizontal_padding=int(self.popup_padding),
                    vertical_padding=int(self.popup_padding),
                )
                self._popup = popup
            except Exception as exc:
                logger.error("HiveNotificationsSummary: failed to create popup: %s", exc)
                self._popup = None

        return self._popup

    def _update_popup_content(self, notifications: Sequence[Dict[str, Any]]) -> None:
        popup = self._ensure_popup()
        if popup is None:
            return

        if not notifications:
            content = "<b>No notifications</b>"
        else:
            lines: List[str] = []
            for notif in notifications[:10]:
                notif_type, sender, date_str, message = _extract_notification_details(notif)
                icon = _NOTIFICATION_TYPE_ICONS.get(notif_type, "•")
                lines.append(
                    f"<b>{icon} {sender}</b> — {message}<span foreground=\"#888888\">  {date_str}</span>"
                )
            if len(notifications) > 10:
                lines.append(f"… {len(notifications) - 10} more")
            content = "\n".join(lines)

        popup.clear()
        popup.layout.text = content
        popup.draw_text()
        popup.draw()
        if self._popup_visible:
            popup.unhide()
            popup.place()

    def _place_popup(self) -> None:
        popup = self._ensure_popup()
        if popup is None:
            return

        if self.bar.horizontal:
            x = self.bar.x + int(self.offsetx)
            y = self.bar.y + self.bar.height
        else:
            x = self.bar.x + self.bar.width
            y = self.bar.y + int(self.offsety)

        popup.x = x
        popup.y = y
        popup.place()

    def show_popup(self) -> None:
        popup = self._ensure_popup()
        if popup is None:
            return
        self._place_popup()
        popup.unhide()
        popup.place()
        popup.draw()
        self._popup_visible = True

    def hide_popup(self) -> None:
        if self._popup is None:
            return
        self._popup.hide()
        self._popup_visible = False

    def toggle_popup(self) -> None:
        if not self.popup_enabled:
            return
        if self._popup_visible:
            self.hide_popup()
        else:
            self.show_popup()

    @expose_command()
    def mark_as_read(self) -> str:
        """Attempt to mark unread notifications as read using ACTIVE WIF."""

        if not self.only_unread:
            return "mark_as_read skipped; only_unread=False"

        env_var = getattr(self, "active_wif_env", None)
        if not env_var:
            return "mark_as_read skipped; no active_wif_env configured"

        wif = os.getenv(env_var)
        if not wif:
            return f"mark_as_read skipped; env {env_var} not set"

        if not self.account:
            return "mark_as_read skipped; account missing"

        try:
            client = Hive(keys=wif, node=self.nodes)
            account = Account(str(self.account), blockchain_instance=client)
            result = account.mark_notifications_as_read()
            logger.info("HiveNotificationsSummary: mark_notifications_as_read result: %s", result)
            self._notifications = []
            self._last_fetch = 0.0
            self.force_update()
            return "Notifications marked as read"
        except Exception as exc:
            logger.error("HiveNotificationsSummary: failed to mark notifications as read: %s", exc)
            return f"mark_as_read failed: {exc}"

    def finalize(self) -> None:
        try:
            self.hide_popup()
            if self._popup is not None:
                self._popup.kill()
        except Exception:
            pass
        self._popup = None
        super().finalize()


class HiveNotificationsList(GenPollText):
    """Render a short list of recent Hive notifications."""

    defaults = [
        ("max_items", 5, "Maximum number of notifications to display."),
        (
            "line_format",
            "{icon} {sender}: {message}",
            "Format string for each notification line.",
        ),
        ("timestamp_format", "%H:%M", "strftime format for timestamps."),
        (
            "separator",
            "\n",
            "Separator between notification lines.",
        ),
        (
            "no_notifications_text",
            "No notifications",
            "Text to show when there are no notifications to list.",
        ),
        (
            "browser_command",
            "qutebrowser",
            "Browser command to open notification URLs.",
        ),
        (
            "base_url",
            "https://peakd.com",
            "Base URL to prepend when notification URLs start with @username.",
        ),
    ]

    def __init__(self, summary: Optional[HiveNotificationsSummary] = None, **config: Any) -> None:
        super().__init__(**config)
        self.add_defaults(HiveNotificationsList.defaults)
        self.summary = summary
        self._cached_notifications: List[Dict[str, Any]] = []

        if self.summary is not None:
            self.summary.register_listener(self)

    def finalize(self) -> None:
        if self.summary is not None:
            self.summary.unregister_listener(self)
        super().finalize()

    def poll(self) -> str:
        if self.summary is None:
            return self.no_notifications_text

        notifications = self.summary.get_notifications()
        self._cached_notifications = notifications

        if not notifications:
            return self.no_notifications_text

        lines: List[str] = []
        for idx, notif in enumerate(notifications[: int(self.max_items) or 5]):
            notif_type, sender, date_str, message = _extract_notification_details(notif)
            icon = _NOTIFICATION_TYPE_ICONS.get(notif_type, "•")
            line = self.line_format.format(
                index=idx,
                icon=icon,
                type=notif_type,
                sender=sender,
                date=date_str,
                time=_short_time(date_str, self.timestamp_format),
                message=message,
            )
            lines.append(line)

        if len(notifications) > len(lines):
            lines.append(f"… {len(notifications) - len(lines)} more")

        return self.separator.join(lines)

    def refresh_from_summary(self) -> None:
        def _update() -> None:
            try:
                text = self.poll()
                self.update(text)
            except Exception as exc:  # pragma: no cover - defensive log
                logger.error("HiveNotificationsList: failed to refresh: %s", exc)

        try:
            self.timeout_add(0, _update)
        except Exception as exc:  # pragma: no cover - defensive log
            logger.error("HiveNotificationsList: timeout_add failed: %s", exc)

    @expose_command()
    def open_notification(self, index: int = 0) -> str:
        if self.summary is None:
            return "No summary widget linked"

        if not self.qtile:
            return "Qtile instance not ready"

        notifications = self.summary.get_notifications()
        if not notifications:
            return "No notifications to open"

        try:
            notif = notifications[int(index)]
        except (IndexError, ValueError):
            return f"Invalid notification index: {index}"

        url = str(notif.get("url") or "")
        if not url:
            return "Notification has no URL"

        if url.startswith("@"):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('@')}"

        try:
            self.qtile.cmd_spawn(f"{self.browser_command} {url}")
            return f"Opened {url}"
        except Exception as exc:
            logger.error("HiveNotificationsList: failed to open url %s: %s", url, exc)
            return f"Failed to open {url}: {exc}"


def _short_time(date_str: str, fmt: str) -> str:
    if not date_str:
        return ""
    try:
        from datetime import datetime

        parsed = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        return parsed.strftime(fmt)
    except Exception:
        return date_str
