"""
HiveRewards Qtile widget

Displays the current unclaimed reward balances for a Hive account using the
`hive-nectar` (nectar) library. No WIF is required for read-only queries.

Example usage in `config.py`:

    import sys
    from os.path import expanduser
    sys.path.insert(0, expanduser("~/.config/qtile/widgets"))

    from hive_rewards import HiveRewards

    HiveRewards(
        account="your-hive-account",
        update_interval=300,  # seconds
        foreground=colors["color2"],
        background=colors["background"],
        padding=5,
    )

"""
from typing import Any, Optional

from libqtile.log_utils import logger
from libqtile.widget.generic_poll_text import GenPollText

# nectar is provided by the hive-nectar package
from nectar import Hive
from nectar.account import Account
from nectar.nodelist import NodeList


class HiveRewards(GenPollText):
    """Poll Hive for unclaimed reward balances and render as text.

    Shows the following Account fields:
      - reward_hive_balance (HIVE)
      - reward_hbd_balance (HBD)
      - reward_vesting_balance (VESTS)

    Note: "reward_vesting_balance" is denominated in VESTS. Converting to HP
    requires blockchain props; this widget displays the raw VESTS value for
    simplicity.
    """

    defaults = [
        (
            "account",
            None,
            "Hive account name to query (required).",
        ),
        (
            "format",
            "R: {hive} | {hbd} | {vests}",
            "Python format string for display. Variables: {hive}, {hbd}, {vests}.",
        ),
        (
            "error_text",
            "Rewards: Error",
            "Text to display when a retrieval/parsing error occurs.",
        ),
        (
            "update_interval",
            300,
            "Seconds between polls.",
        ),
        (
            "nodes",
            ["https://api.syncad.com", "https://api.hive.blog"],
            "List of Hive node URLs to use.",
        ),
    ]

    def __init__(self, **config: Any) -> None:
        # GenPollText expects keyword-only config; do not pass positional text
        super().__init__(**config)
        self.add_defaults(HiveRewards.defaults)
        # Start with empty text until first poll
        try:
            self.update("")
        except Exception:
            # Defensive: not all versions expose update() identically
            pass

        # Client handles
        self._hive: Optional[Hive] = None
        self._account: Optional[Account] = None

        # Validate required parameters
        if not getattr(self, "account", None):
            logger.error("HiveRewards: 'account' is required.")

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------
    def _ensure_client(self) -> bool:
        """Ensure Hive and Account instances are initialized."""
        if self._hive is None:
            try:
                # Initialize node list once; nectar internally handles failover
                try:
                    n = NodeList()
                    n.update_nodes()
                    n.get_hive_nodes()
                except Exception as e:
                    # Non-fatal; we still proceed with provided nodes
                    logger.debug("HiveRewards: NodeList update failed: %s", e)

                self._hive = Hive(node=self.nodes)
            except Exception as e:
                logger.error("HiveRewards: Failed to initialize Hive client: %s", e)
                self._hive = None
                return False

        if self._account is None and self._hive is not None and self.account:
            try:
                self._account = Account(self.account, blockchain_instance=self._hive)
            except Exception as e:
                logger.error("HiveRewards: Failed to initialize Account '%s': %s", self.account, e)
                self._account = None
                return False

        return self._account is not None

    # ------------------------------------------------------------------
    # GenPollText hook
    # ------------------------------------------------------------------
    def poll(self) -> str:
        """Return the text to display for the widget."""
        if not self.account:
            return self.error_text

        if not self._ensure_client():
            return self.error_text

        try:
            # Access reward balances via mapping interface on Account
            # These are nectar.Amount types which stringify nicely (e.g. "0.000 HIVE").
            rh = self._account["reward_hive_balance"]
            rbd = self._account["reward_hbd_balance"]
            rvests = self._account["reward_vesting_balance"]

            variables = {
                "hive": str(rh),
                "hbd": str(rbd),
                "vests": str(rvests),
            }
            return self.format.format(**variables)
        except Exception as e:
            logger.error("HiveRewards: Error retrieving rewards for '%s': %s", self.account, e)
            return self.error_text
