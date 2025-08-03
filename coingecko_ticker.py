"""coingecko_ticker.py

A Qtile widget similar to `CryptoTicker` but using the CoinGecko API so that it
works in regions where Coinbase or Binance APIs may be inaccessible.

The widget keeps the familiar interface of `CryptoTicker`: you can specify the
cryptocurrency symbol, the fiat currency you want prices in, a formatting
string and a symbol for your fiat currency. The *only* change is that data is
fetched from CoinGecko's public API.

Example usage (in your `config.py`):

    from qtile_extras.widget.coingecko_ticker import CoinGeckoTicker

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
from typing import Any, Dict

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

_API_URL = (
    "https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies={currency}"
)


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
    ]

    def __init__(self, **config: Any):
        super().__init__(**config)
        self.add_defaults(CoinGeckoTicker.defaults)

        # Fallbacks in case locale info is not set
        if not self.currency:
            self.currency = "USD"
        if not self.symbol:
            self.symbol = "$"

    # ---------------------------------------------------------------------
    # GenPollUrl hooks
    # ---------------------------------------------------------------------
    @property
    def url(self) -> str:
        # CoinGecko expects lowercase query params
        currency = self.currency.lower()
        crypto_id = self._get_crypto_id().lower()
        return _API_URL.format(ids=crypto_id, currency=currency)

    def parse(self, body: Dict[str, Any]) -> str:
        """Parse CoinGecko JSON response and format for display."""
        crypto_id = self._get_crypto_id().lower()
        currency_key = self.currency.lower()

        try:
            price = float(body[crypto_id][currency_key])
        except (KeyError, TypeError, ValueError) as e:
            logger.error("CoinGeckoTicker: failed to parse response: %s", e)
            return f"{self.crypto}: Error"

        variables = {
            "crypto": self.crypto.upper(),
            "symbol": self.symbol,
            "amount": price,
        }
        return self.format.format(**variables)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
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
