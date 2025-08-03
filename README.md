# Qtile Widgets

## CoinGeckoTicker Qtile Widget

Provides real-time prices for any cryptocurrency listed on CoinGecko. It keeps the same interface as Qtile's built-in `CryptoTicker` but avoids Coinbase/Binance limits—ideal for HIVE or when those APIs are blocked.

### CoinGeckoTicker Installation

1. Copy `coingecko_ticker.py` into `~/.config/qtile/widgets/`.
2. Ensure `~/.config/qtile/widgets/__init__.py` exists (can be empty).

### CoinGeckoTicker Configuration

Add the widgets directory to your `PYTHONPATH` and import the widget in `config.py`:

```python
import sys
from os.path import expanduser
sys.path.insert(0, expanduser("~/.config/qtile/widgets"))

from coingecko_ticker import CoinGeckoTicker
```

Then add `CoinGeckoTicker` to your bar:

```python
from libqtile import bar, widget, Screen

screens = [
    Screen(
        bottom=bar.Bar(
            [
                # other widgets …
                CoinGeckoTicker(
                    crypto="HIVE",          # any CoinGecko-listed coin
                    update_interval=60,      # seconds
                    fontsize=10,
                    foreground=colors["green"],
                    background=colors["background"],
                    padding=5,
                ),
                # other widgets …
            ],
            24,
        ),
    ),
]
```

`update_interval` defaults to 60 seconds; adjust as needed.

This widget uses CoinGecko's public API—no API key required.
