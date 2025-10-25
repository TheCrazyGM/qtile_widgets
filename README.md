# Qtile Widgets

Custom Qtile widgets packaged for easy reuse. Install them directly into the
environment Qtile runs under and import the modules like any other Python
package.

## Installation

```bash
uv pip install -e .
```

The editable install exposes the modules under `widgets.*`. Any runtime
dependencies (e.g. `hive-nectar` for Hive-related widgets) are declared in
`pyproject.toml`.

## Available widgets

### `widgets.coingecko_ticker.CoinGeckoTicker`

Cryptocurrency ticker backed by the CoinGecko "simple price" API.

- Supports automatic ID mapping and immutable config compatible with Qtile's
  built-in `CryptoTicker`.
- Optional 24 h change display with dynamic colours (`foreground_up`,
  `foreground_down`, `foreground_zero`).
- Accepts standard `GenPollUrl` options (`update_interval`, `format`, etc.).

```python
from widgets.coingecko_ticker import CoinGeckoTicker

CoinGeckoTicker(
    crypto="HIVE",
    show_change=True,
    format_with_change="{crypto}: {symbol}{amount:.3f} ({change:+.2f}%)",
    foreground_up="#50FA7B",
    foreground_down="#FF5555",
)
```

### `widgets.custom_mpris2.CustomMpris2`

Drop-in replacement for Qtile's `Mpris2` widget that hides separators when
artist/title metadata is missing.

```python
from widgets.custom_mpris2 import CustomMpris2

CustomMpris2(format="{xesam:artist} – {xesam:title}")
```

### `widgets.hive_rewards.HiveRewards`

Displays unclaimed Hive reward balances (HIVE/HBD/VESTS) using the
[`hive-nectar`](https://github.com/thecrazygm/hive-nectar) library.

- Requires `hive-nectar` (pulled in automatically via dependency).
- Provides `format` option with variables `{hive}`, `{hbd}`, `{vests}`.
- Exposes a `refresh` command to trigger immediate updates.

```python
from widgets.hive_rewards import HiveRewards

HiveRewards(account="thecrazygm", update_interval=300)
```

### `widgets.now_playing.NowPlaying`

Polls a JSON endpoint for "now playing" data (e.g. SiriusXM) and renders a
formatted string.

- Caches an `aiohttp.ClientSession` for efficient polling.
- Offers verbose/non-verbose formats, optional truncation via `max_chars`, and
  `set_channel`/`get_channel` commands.

```python
from widgets.now_playing import NowPlaying

NowPlaying(channel="octane", update_interval=5)
```

### `widgets.qtile_hive_widget.HivePrice`

Simple CoinGecko-backed price widget tailored for HIVE.

```python
from widgets.qtile_hive_widget import HivePrice

HivePrice(update_interval=120)
```

### `widgets.swallow`

Helper functions for implementing terminal window swallowing in Qtile via
hooks (`handle_client_new`, `handle_client_killed`).

```python
from widgets.swallow import handle_client_new, handle_client_killed

@hook.subscribe.client_new
def _swallow(c):
    handle_client_new(c)

@hook.subscribe.client_killed
def _unswallow(c):
    handle_client_killed(c)
```

Set `SWALLOW_NOTIFY = False` in `widgets.swallow` if you want to disable the
"terminal restored" desktop notification, or adjust `SWALLOW_NOTIFY_TITLE` and
`SWALLOW_NOTIFY_TIMEOUT` to suit your preference.

### `widgets.hive_notifications`

Compact badge that polls Hive for unread notifications and displays a count.

```python
from widgets.hive_notifications import HiveNotifications

hive_notifications = HiveNotifications(
    account="thecrazygm",
    update_interval=300,
)

widgets = [hive_notifications]
```

Call `qtile cmd-obj -o widget hive_notifications -f mark_as_read` to clear
unread items (requires the `ACTIVE_WIF` environment variable to be set).

## Development notes

- A `py.typed` marker is included so type checkers recognise inline typing.
- Run checks via `uv tool run ruff check --fix` and `uv tool run ty check`.
