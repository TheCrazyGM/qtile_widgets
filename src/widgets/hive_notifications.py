"""Hive notifications count widget for Qtile bars."""

import os
import time
from typing import Any, Dict, List, Optional, Sequence, TYPE_CHECKING

from libqtile.command.base import expose_command
from libqtile.log_utils import logger
from libqtile.widget.generic_poll_text import GenPollText

from nectar import Hive
from nectar.account import Account
from nectar.nodelist import NodeList

if TYPE_CHECKING:
    from libqtile.bar import Bar
    from libqtile.core.manager import Qtile


_HIVE_DEFAULT_NODES: Sequence[str] = (
    "https://api.syncad.com",
    "https://api.hive.blog",
)

 


class HiveNotifications(GenPollText):
    """Display the count of unread Hive notifications."""

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
    ]

    def __init__(self, **config: Any) -> None:
        super().__init__(**config)
        self.add_defaults(HiveNotifications.defaults)
        self._hive: Optional[Hive] = None
        self._account: Optional[Account] = None
        self._notifications: List[Dict[str, Any]] = []
        self._last_fetch: float = 0.0

        if not getattr(self, "account", None):
            logger.error("HiveNotifications: 'account' is required")

    def _configure(self, qtile: Qtile, bar: Bar) -> None:
        super()._configure(qtile, bar)
        self.timeout_add(0, self.force_update)

    def poll(self) -> str:
        try:
            notifications = self._fetch_notifications(force=True)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("HiveNotifications: poll failed: %s", exc)
            return self.error_text

        count = len(notifications)
        return self.format.format(count=count) if count else self.empty_text

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
            logger.error("HiveNotifications: failed to mark notifications as read: %s", exc)
            return f"mark_as_read failed: {exc}"
