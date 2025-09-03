# Qtile Widgets

## CustomMpris2 Qtile Widget

An enhanced MPRIS2 widget that dynamically hides the artist/title and separator when either the artist or title metadata is missing, providing a cleaner display for media players with incomplete metadata.

### CustomMpris2 Installation

1. Copy `custom_mpris2.py` into `~/.config/qtile/widgets/`.
2. Ensure `~/.config/qtile/widgets/__init__.py` exists (can be empty).

### CustomMpris2 Configuration

Add the widgets directory to your `PYTHONPATH` and import the widget in `config.py`:

```python
import sys
from os.path import expanduser
sys.path.insert(0, expanduser("~/.config/qtile/widgets"))

from custom_mpris2 import CustomMpris2
```

Then add `CustomMpris2` to your bar:

```python
from libqtile import bar, widget, Screen

screens = [
    Screen(
        bottom=bar.Bar(
            [
                # other widgets ...
                CustomMpris2(
                    name='mpd',  # or any other MPRIS2-compatible player
                    objname="org.mpris.MediaPlayer2.mpd",
                    format='{xesam:artist} - {xesam:title}',
                    scroll_chars=None,
                    stop_pause_text='',
                    **your_style_here
                ),
                # other widgets ...
            ],
            24,
        ),
    ),
]
```

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
