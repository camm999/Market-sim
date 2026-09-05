# simulator/agent.py
"""shared position-keeping for every trading agent in the sim."""

from typing import List, Tuple

from lob.book import LimitOrderBook, Side


class Agent:
    """
    holds the two things every agent in this project tracks: a net position
    and the cash flow that built it, plus the mark-to-market that combines them.

    deliberately does *not* hold `max_inventory`: MarketMaker and
    ImbalanceTrader always cap themselves, while InformedTrader defaults to
    uncapped, so the risk limit belongs to each subclass rather than here.
    """

    def __init__(self) -> None:
        self.inventory = 0  # net position: +long, -short
        self.cash = 0.0  # running cash flow from fills

    def mark_to_market(self, book: LimitOrderBook) -> float:
        """cash plus the value of current inventory at the current mid price."""
        return self.cash + self.inventory * book.mid_price()  # position value at mid price

    def _apply_trades(self, trades: List[Tuple[float, int]], side: Side) -> None:
        """book a list of (price, size) fills onto inventory and cash."""
        filled = sum(size for _, size in trades)
        if filled == 0:
            return

        avg_price = sum(price * size for price, size in trades) / filled

        if side == "buy":
            self.inventory += filled
            self.cash -= filled * avg_price
        else:
            self.inventory -= filled
            self.cash += filled * avg_price


class MarketTakingAgent(Agent):
    """an agent that expresses its view by crossing the spread with market orders."""

    size: int  # market order size sent per trade; set by each subclass

    def _execute_market_order(self, book: LimitOrderBook, side: Side) -> None:
        """send a market order and work out what it actually filled from the new trades."""
        start = len(book.trades)
        book.add_market_order(side, self.size)
        self._apply_trades(book.trades[start:], side)
