"""
A Qtile widget to display the current HIVE price using GenPollUrl.
"""

from libqtile.widget import GenPollUrl


def parse_hive_price(response):
    """Extract and format Hive price from CoinGecko JSON response."""
    try:
        price = float(response["hive"]["usd"])
        return f"HIVE: ${price:.2f}"
    except (KeyError, TypeError, ValueError):
        return "HIVE: Error"


class HivePrice(GenPollUrl):
    """
    A Qtile widget that polls the CoinGecko API for the current HIVE price.
    """

    def __init__(self, **config):
        super().__init__(
            url="https://api.coingecko.com/api/v3/simple/price?ids=hive&vs_currencies=usd",
            json=True,
            parse=parse_hive_price,
            **config,
        )
