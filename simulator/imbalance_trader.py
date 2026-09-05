# simulator/imbalance_trader.py

from typing import Optional

from lob.book import LimitOrderBook
from simulator.agent import MarketTakingAgent


class ImbalanceTrader(MarketTakingAgent):
    """
    simple momentum trader that reacts to order book imbalance.

    this agent leans WITH the book's imbalance: when there's much
    more resting size on the bid than the ask, that pressure often
    precedes the price getting pushed up, so it hits the market with a
    buy to ride that move, vice versa for ask imbalance.

    `depth_levels` picks how much of the book counts toward that imbalance.
    `None` (the default) uses the whole book, which is what every result in
    ANALYSIS.md was produced with. A small integer (`depth_levels=5`) uses only
    the n best levels on each side, which is closer to how imbalance is measured
    on a real venue - size resting 40 ticks away is never going to trade, so
    counting it dilutes the signal the agent is actually trying to read.
    """

    def __init__(
        self,
        threshold: float = 0.4,
        size: int = 5,
        max_inventory: int = 50,
        depth_levels: Optional[int] = None,
    ) -> None:
        super().__init__()
        self.threshold = threshold  # imbalance magnitude required to act
        self.size = size  # market order size per trade
        self.max_inventory = max_inventory  # risk limit
        self.depth_levels = depth_levels  # price levels per side to measure over; None = whole book

    def _imbalance(self, book: LimitOrderBook) -> float:
        return book.imbalance(self.depth_levels)

    def act(self, book: LimitOrderBook) -> None:
        """check the book's imbalance and, if it's strong enough, trade with it."""
        imbalance = self._imbalance(book)

        if imbalance > self.threshold and self.inventory < self.max_inventory:
            self._execute_market_order(book, "buy")

        elif imbalance < -self.threshold and self.inventory > -self.max_inventory:
            self._execute_market_order(book, "sell")
