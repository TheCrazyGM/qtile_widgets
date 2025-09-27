"""
Terminal swallowing utilities for Qtile (X11).

Behavior
- When a GUI app is spawned from a terminal, minimize the terminal while the GUI is open.
- When the GUI is closed, restore and focus the terminal.

Usage
- Place this file in ~/.config/qtile/widgets/swallow.py
- In your config.py: `from swallow import handle_client_new, handle_client_killed`
- Then wire hooks in config.py:

    @hook.subscribe.client_new
    def swallow_on_client_new(c):
        handle_client_new(c)

    @hook.subscribe.client_killed
    def unswallow_on_client_killed(c):
        handle_client_killed(c)

Notes
- Works by walking the new client's process tree to find a parent terminal window.
- Restricts swallowing to a known set of terminal WM_CLASS names. Adjust SWALLOW_TERMINALS if needed.
"""

from typing import Iterable, Optional

from libqtile import qtile
from libqtile.log_utils import logger

# Enable/disable swallowing globally
SWALLOW_ENABLED = True

# Known terminal WM_CLASS values. You can extend this list to suit your setup.
SWALLOW_TERMINALS = {
    "Alacritty",
    "kitty",
    "WezTerm",
    "wezterm",
    "st-256color",
    "st",
    "XTerm",
    "URxvt",
    "Terminator",
    "tilix",
    "qterminal",
    "konsole",
    "gnome-terminal",
    "foot",
}

# Maximum number of parent hops when walking the process tree
MAX_ANCESTRY_DEPTH = 8


def _get_ppid(pid: int) -> Optional[int]:
    """Return parent PID from /proc/<pid>/status or None if unavailable."""
    try:
        with open(f"/proc/{pid}/status", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("PPid:"):
                    try:
                        return int(line.split()[-1])
                    except ValueError:
                        return None
    except Exception:
        return None
    return None


def _get_ancestry(pid: int, limit: int = MAX_ANCESTRY_DEPTH) -> Iterable[int]:
    """Yield PIDs from child->...->root up to `limit` steps (exclusive of 0/1)."""
    seen = set()
    current = pid
    for _ in range(limit):
        ppid = _get_ppid(current)
        if not ppid or ppid in seen or ppid <= 1:
            break
        yield ppid
        seen.add(ppid)
        current = ppid


def _is_terminal_win(win) -> bool:
    try:
        wm_class = win.window.get_wm_class() or ()
        return any(cls in SWALLOW_TERMINALS for cls in wm_class)
    except Exception:
        return False


def _is_terminal_client(client) -> bool:
    try:
        wm_class = client.window.get_wm_class() or ()
        return any(cls in SWALLOW_TERMINALS for cls in wm_class)
    except Exception:
        return False


def handle_client_new(client):
    if not SWALLOW_ENABLED:
        logger.debug("Swallow: disabled; skipping client_new")
        return

    # If the new client itself is a terminal, do not swallow.
    if _is_terminal_client(client):
        logger.debug("Swallow: new client is a terminal; skipping")
        return

    try:
        pid = client.window.get_net_wm_pid()
    except Exception:
        pid = None

    if not pid:
        logger.debug("Swallow: client has no PID; skipping")
        return

    logger.debug(
        "Swallow: handling client_new pid=%s wm_class=%s",
        pid,
        getattr(client.window, "get_wm_class", lambda: ())(),
    )

    # Map PIDs to potential terminal windows.
    winmap = list(qtile.windows_map.values())

    ancestry = list(_get_ancestry(int(pid)))
    logger.debug("Swallow: ancestry for pid %s -> %s", pid, ancestry)

    parent_term = None
    for anc_pid in ancestry:
        logger.debug("Swallow: checking ancestor pid=%s", anc_pid)
        for w in winmap:
            try:
                wpid = w.window.get_net_wm_pid()
            except Exception:
                continue
            if not wpid or int(wpid) != int(anc_pid):
                continue
            wclass = None
            try:
                wclass = w.window.get_wm_class()
            except Exception:
                wclass = None
            logger.debug(
                "Swallow: found window for anc_pid=%s with wm_class=%s", wpid, wclass
            )
            if _is_terminal_win(w):
                logger.debug("Swallow: selected parent terminal window for pid=%s", pid)
                parent_term = w
                break
        if parent_term:
            break

    if not parent_term:
        logger.debug("Swallow: no parent terminal found for pid=%s", pid)
        return

    try:
        if not getattr(parent_term, "minimized", False):
            logger.debug("Swallow: minimizing parent terminal")
            parent_term.toggle_minimize()
        # link for restoration when child dies
        setattr(client, "_swallowed_parent", parent_term)
        logger.debug("Swallow: linked parent terminal for restoration")
    except Exception as e:
        logger.warning("Swallow: failed to minimize parent terminal: %s", e)


def handle_client_killed(client):
    parent = getattr(client, "_swallowed_parent", None)
    if not parent:
        logger.debug("Swallow: no linked parent on client_killed; skipping restore")
        return

    try:
        if getattr(parent, "minimized", False):
            logger.debug("Swallow: restoring minimized parent terminal")
            parent.toggle_minimize()
        # Focus the parent in its group
        if parent.group:
            logger.debug("Swallow: focusing parent terminal in its group")
            parent.group.focus(parent, False)
    except Exception as e:
        logger.warning("Swallow: failed to restore parent terminal: %s", e)
