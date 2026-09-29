"""coingecko_ticker.py

A Qtile widget similar to `CryptoTicker` but using the CoinGecko API so that it
works in regions where Coinbase or Binance APIs may be inaccessible.

The widget keeps the familiar interface of `CryptoTicker`: you can specify the
cryptocurrency symbol, the fiat currency you want prices in, a formatting
string and a symbol for your fiat currency. The *only* change is that data is
fetched from CoinGecko's public API.

Example usage (in your `config.py`):

    from widget.coingecko_ticker import CoinGeckoTicker

    widgets = [
        CoinGeckoTicker(),                             # BTC -> local currency
        CoinGeckoTicker(crypto="HIVE"),              # HIVE in local currency
        CoinGeckoTicker(crypto="ETH", currency="EUR", symbol="€"),
    ]

Limitations
-----------
CoinGecko uses *ids* (e.g. "bitcoin", "ethereum") not ticker symbols ("BTC",
"ETH").  A minimal mapping is included for popular coins and you can override
it via the ``crypto_id`` kwarg if the default mapping does not suit your
needs.
"""

import asyncio
import locale
import os
from typing import Any

import aiohttp
from aiohttp.client_exceptions import ClientError, ContentTypeError
from libqtile.confreader import ConfigError
from libqtile.log_utils import logger
from libqtile.widget.gen_poll_url import GenPollUrl

_DEFAULT_CURRENCY = str(locale.localeconv()["int_curr_symbol"]).strip() or "USD"
_DEFAULT_SYMBOL = str(locale.localeconv()["currency_symbol"]) or "$"

# Minimal mapping between common ticker symbols and CoinGecko IDs.
# Users can extend/override this with the ``crypto_id`` kwarg.
_DEFAULT_ID_MAP: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "LTC": "litecoin",
    "HIVE": "hive",
    "BNB": "binancecoin",
    "SOL": "solana",
    "ADA": "cardano",
    "DOGE": "dogecoin",
}

_API_URL = "https://api.coingecko.com/api/v3/simple/price"
_CHANGE_SUFFIX = "_24h_change"


class CoinGeckoTicker(GenPollUrl):
    """A cryptocurrency ticker that fetches prices from CoinGecko."""

    defaults = [  # noqa: RUF012
        (
            "currency",
            _DEFAULT_CURRENCY,
            "Fiat currency that the crypto value is displayed in (e.g. USD, EUR).",
        ),
        ("symbol", _DEFAULT_SYMBOL, "Symbol for the fiat currency (e.g. $ / €)."),
        (
            "crypto",
            "BTC",
            "Ticker symbol of the cryptocurrency (e.g. BTC, ETH, HIVE).",
        ),
        (
            "format",
            "{crypto}: {symbol}{amount:.2f}",
            "Python format string for display.",
        ),
        (
            "crypto_id",
            None,
            "Override the CoinGecko *id* if it can't be derived from the ticker symbol.",
        ),
        (
            "id_map",
            _DEFAULT_ID_MAP,
            "Mapping dict from ticker symbols to CoinGecko IDs.",
        ),
        (
            "show_change",
            False,
            "Show 24h percentage change when available.",
        ),
        (
            "format_with_change",
            "{crypto}: {symbol}{amount:.2f} ({change:+.2f}%)",
            "Format string used when show_change is True and change data is available.",
        ),
        (
            "foreground_up",
            None,
            "Hex colour for positive change (falls back to widget foreground).",
        ),
        (
            "foreground_down",
            None,
            "Hex colour for negative change (falls back to widget foreground).",
        ),
        (
            "foreground_zero",
            None,
            "Hex colour for neutral change (falls back to widget foreground).",
        ),
        (
            "change_neutral_threshold",
            0.0,
            "Absolute 24h change (in %) treated as neutral when <= threshold.",
        ),
        (
            "api_key",
            None,
            "CoinGecko API key (Demo or Pro). If None, checks COINGECKO_API_KEY environment variable.",
        ),
        (
            "is_pro",
            False,
            "Whether the API key is a Pro API key (uses pro-api.coingecko.com).",
        ),
        (
            "retain_on_error",
            True,
            "Keep the last successfully fetched price if a temporary error occurs.",
        ),
    ]

    def __init__(self, **config: Any):
        config.setdefault("json", True)
        super().__init__(**config)
        self.add_defaults(CoinGeckoTicker.defaults)

        # Fallbacks in case locale info is not set
        if not self.currency:
            self.currency = "USD"
        if not self.symbol:
            self.symbol = "$"
        if self.api_key is None:
            self.api_key = os.environ.get("COINGECKO_API_KEY")
        self._base_foreground: str | None = None
        self._last_rendered: str | None = None
        self._session: aiohttp.ClientSession | None = None

    # ---------------------------------------------------------------------
    # GenPollUrl hooks
    # ---------------------------------------------------------------------
    @property
    def url(self) -> str:
        base = "https://pro-api.coingecko.com/api/v3/simple/price" if self.is_pro else _API_URL
        currency = self.currency.lower()
        crypto_id = self._get_crypto_id().lower()
        query = f"?ids={crypto_id}&vs_currencies={currency}"
        if self._needs_change():
            query += "&include_24hr_change=true"
        return f"{base}{query}"

    async def apoll(self) -> str:
        """Fetch price from CoinGecko with graceful error handling and API key support."""
        if not self.parse or not self.url:
            return "Invalid config"

        headers = self.headers.copy()
        if self.api_key:
            header_name = "x-cg-pro-api-key" if self.is_pro else "x-cg-demo-api-key"
            headers[header_name] = self.api_key
        headers.setdefault("User-Agent", "Mozilla/5.0 (compatible; QtileCoinGeckoTicker/1.0)")
        headers.setdefault("Accept", "application/json")

        try:
            session = await self._get_session()
            async with session.request(
                method="GET", url=self.url, headers=headers
            ) as response:
                if response.status == 429:
                    logger.warning(
                        "CoinGeckoTicker (%s): rate limited (HTTP 429).",
                        self.crypto,
                    )
                    return (
                        self._last_rendered
                        if (self.retain_on_error and self._last_rendered)
                        else f"{self.crypto}: Rate Limited"
                    )

                if response.status in (401, 403):
                    logger.warning(
                        "CoinGeckoTicker (%s): access blocked (HTTP %s). CoinGecko requires an API key.",
                        self.crypto,
                        response.status,
                    )
                    return (
                        self._last_rendered
                        if (self.retain_on_error and self._last_rendered)
                        else f"{self.crypto}: Key Req"
                    )

                if response.status >= 400:
                    logger.warning(
                        "CoinGeckoTicker (%s): request to %s returned HTTP %s",
                        self.crypto,
                        self.url,
                        response.status,
                    )
                    return (
                        self._last_rendered
                        if (self.retain_on_error and self._last_rendered)
                        else f"{self.crypto}: Err {response.status}"
                    )

                content_type = response.headers.get("Content-Type", "")
                if "json" not in content_type.lower():
                    logger.warning(
                        "CoinGeckoTicker (%s): unexpected content type '%s' from %s",
                        self.crypto,
                        content_type,
                        self.url,
                    )
                    return (
                        self._last_rendered
                        if (self.retain_on_error and self._last_rendered)
                        else f"{self.crypto}: Err"
                    )

                try:
                    body = await response.json()
                except ContentTypeError as e:
                    logger.warning(
                        "CoinGeckoTicker (%s): JSON decoding failed: %s",
                        self.crypto,
                        e,
                    )
                    return (
                        self._last_rendered
                        if (self.retain_on_error and self._last_rendered)
                        else f"{self.crypto}: Err"
                    )

            if not isinstance(body, dict):
                logger.error(
                    "CoinGeckoTicker (%s): expected dict response, got %s",
                    self.crypto,
                    type(body).__name__,
                )
                return (
                    self._last_rendered
                    if (self.retain_on_error and self._last_rendered)
                    else f"{self.crypto}: Err"
                )

            text = self.parse(body)
            if not text.endswith(": Error"):
                self._last_rendered = text
            return text

        except (TimeoutError, ClientError) as e:
            logger.warning("CoinGeckoTicker (%s): request failed: %s", self.crypto, e)
            return (
                self._last_rendered
                if (self.retain_on_error and self._last_rendered)
                else f"{self.crypto}: Err"
            )
        except Exception:  # noqa: BLE001
            logger.exception("CoinGeckoTicker (%s): unexpected error polling widget", self.crypto)
            return (
                self._last_rendered
                if (self.retain_on_error and self._last_rendered)
                else f"{self.crypto}: Err"
            )

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
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
        try:
            super().finalize()
        except AttributeError:
            pass

    def _configure(self, qtile, bar):
        super()._configure(qtile, bar)
        # Capture the initial foreground so dynamic colour changes can restore it.
        self._base_foreground = self.foreground

    def parse(self, body: dict[str, Any]) -> str:
        """Parse CoinGecko JSON response and format for display."""
        crypto_id = self._get_crypto_id().lower()
        currency_key = self.currency.lower()

        try:
            crypto_data = body[crypto_id]
            price = float(crypto_data[currency_key])
        except (KeyError, TypeError, ValueError) as e:
            logger.error("CoinGeckoTicker: failed to parse response: %s", e)
            self._apply_change_colour(None)
            return f"{self.crypto}: Error"

        change: float | None = None
        if self._needs_change():
            change_key = f"{currency_key}{_CHANGE_SUFFIX}"
            raw_change = crypto_data.get(change_key)
            if raw_change is not None:
                try:
                    change = float(raw_change)
                except (TypeError, ValueError) as e:
                    logger.warning(
                        "CoinGeckoTicker: invalid 24h change value for %s: %s",
                        self.crypto,
                        e,
                    )
                    change = None

        variables = {
            "crypto": self.crypto.upper(),
            "symbol": self.symbol,
            "amount": price,
        }
        if change is not None:
            variables["change"] = change
            variables["change_abs"] = abs(change)

        self._apply_change_colour(change)

        template = self.format
        if self.show_change and change is not None:
            template = self.format_with_change

        try:
            return template.format(**variables)
        except KeyError as e:
            logger.error("CoinGeckoTicker: format string error: %s", e)
            return (
                f"{variables['crypto']}: {variables['symbol']}{variables['amount']:.2f}"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _needs_change(self) -> bool:
        return self.show_change or any(
            colour is not None
            for colour in (
                self.foreground_up,
                self.foreground_down,
                self.foreground_zero,
            )
        )

    def _get_crypto_id(self) -> str:
        """Return CoinGecko ID for the configured crypto symbol."""
        if self.crypto_id:
            return self.crypto_id

        try:
            return self.id_map[self.crypto.upper()]
        except KeyError:
            logger.error(
                "CoinGeckoTicker: Unknown crypto symbol '%s'. Pass 'crypto_id' kwarg or extend 'id_map'.",
                self.crypto,
            )
            raise ConfigError(
                "Unknown crypto symbol passed to CoinGeckoTicker and no crypto_id provided."
            )

    def _apply_change_colour(self, change: float | None) -> None:
        if self._base_foreground is None:
            self._base_foreground = getattr(self, "foreground", None)

        colour: str | None
        if change is None:
            colour = self._base_foreground
        elif abs(change) <= self.change_neutral_threshold:
            colour = self.foreground_zero or self._base_foreground
        elif change > 0:
            colour = self.foreground_up or self._base_foreground
        else:
            colour = self.foreground_down or self._base_foreground

        if colour:
            if getattr(self, "layout", None):
                self.layout.colour = colour
            self.foreground = colour
