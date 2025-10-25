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

import locale
from typing import Any, Dict, Optional

from libqtile.confreader import ConfigError
from libqtile.log_utils import logger
from libqtile.widget.generic_poll_text import GenPollUrl

_DEFAULT_CURRENCY = str(locale.localeconv()["int_curr_symbol"]).strip() or "USD"
_DEFAULT_SYMBOL = str(locale.localeconv()["currency_symbol"]) or "$"

# Minimal mapping between common ticker symbols and CoinGecko IDs.
# Users can extend/override this with the ``crypto_id`` kwarg.
_DEFAULT_ID_MAP: Dict[str, str] = {
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

    defaults = [
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
        self._base_foreground: Optional[str] = None

    # ---------------------------------------------------------------------
    # GenPollUrl hooks
    # ---------------------------------------------------------------------
    @property
    def url(self) -> str:
        # CoinGecko expects lowercase query params
        currency = self.currency.lower()
        crypto_id = self._get_crypto_id().lower()
        query = f"?ids={crypto_id}&vs_currencies={currency}"
        if self._needs_change():
            query += "&include_24hr_change=true"
        return f"{_API_URL}{query}"

    def _configure(self, qtile, bar):
        super()._configure(qtile, bar)
        # Capture the initial foreground so dynamic colour changes can restore it.
        self._base_foreground = self.foreground

    def parse(self, body: Dict[str, Any]) -> str:
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

        change: Optional[float] = None
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

    def _apply_change_colour(self, change: Optional[float]) -> None:
        if self._base_foreground is None:
            self._base_foreground = getattr(self, "foreground", None)

        colour: Optional[str]
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
