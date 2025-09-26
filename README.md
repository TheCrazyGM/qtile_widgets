# Qtile Widgets

## HivePrice Qtile Widget

Displays the current HIVE price (USD) in your Qtile bar via the CoinGecko API.

### HivePrice Installation

1. Copy `qtile_hive_widget.py` into `~/.config/qtile/widgets/`.
2. Ensure `~/.config/qtile/widgets/__init__.py` exists (can be empty).

### HivePrice Configuration

Add the widgets directory to your `PYTHONPATH` and import the widget in `config.py`:

```python
import sys
from os.path import expanduser
sys.path.insert(0, expanduser("~/.config/qtile/widgets"))

from qtile_hive_widget import HivePrice
```

Then add `HivePrice` to your bar:

```python
from libqtile import bar, widget, Screen

screens = [
    Screen(
        bottom=bar.Bar(
            [
                # other widgets …
                HivePrice(
                    update_interval=300,  # seconds
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

---

This widget uses CoinGecko's public API—no API key required.

---

## HiveRewards Qtile Widget

Displays unclaimed Hive reward balances (HIVE, HBD, VESTS) for a given account using the `hive-nectar` library. Read-only; no WIF required.

### HiveRewards Installation

1. Ensure `hive_rewards.py` is located in `~/.config/qtile/widgets/`.
2. Ensure `~/.config/qtile/widgets/__init__.py` exists (can be empty).
3. Install the nectar library (in the same Python environment Qtile uses):

```bash
pip install --user git+https://github.com/thecrazygm/hive-nectar@main
```

### HiveRewards Configuration

Add the widgets directory to your `PYTHONPATH` and import the widget in `config.py`:

```python
import sys
from os.path import expanduser
sys.path.insert(0, expanduser("~/.config/qtile/widgets"))

from hive_rewards import HiveRewards
```

Then add `HiveRewards` to your bar:

```python
from libqtile import bar, widget, Screen

screens = [
    Screen(
        top=bar.Bar(
            [
                # other widgets …
                HiveRewards(
                    account="your-hive-account",   # required
                    # Optional:
                    # format="{hbd} | {vests}",     # default: "R: {hive} | {hbd} | {vests}"
                    update_interval=300,            # seconds
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

Notes:

- `reward_vesting_balance` is in VESTS. Converting to HP is not performed by default.
- You can customize the `format` string with variables: `{hive}`, `{hbd}`, `{vests}`.

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
