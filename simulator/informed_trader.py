# simulator/informed_trader.py

from typing import List, Optional, Tuple

from lob.book import LimitOrderBook, Side


class InformedTrader:
    """
    fed a ground-truth schedule of future price-drift windows at
    construction, resembles informational edge.
    
    under simulate_random_flow its own order flow is what causes the drift 

    under simulate_historical_flow with a gbm_flow scheduled-drift path, the
    same schedule instead drives an exogenous anchor price, so the drift
    is genuine rather than self-caused.

    tracks step count internally (incremented once per `act()`
    call) rather than taking a step argument, so its call signature
    matches ImbalanceTrader's `act(book)`. assumes `act()` is called
    exactly once per simulation step, in order.

    unlike the other agents, `max_inventory` defaults to None (uncapped):
    risk-capping is a liquidity-provider concept.
    """

    def __init__(
        self,
        schedule: List[Tuple[int, int, Side]],
        size: int = 4,
        max_inventory: Optional[int] = None,
    ) -> None:
        self.schedule = schedule  # (start_step, end_step, side), end exclusive
        self.size = size  # market order size sent each active step
        self.max_inventory = max_inventory  # risk cap; None = uncapped

        self.inventory = 0  # net position: +long, -short
        self.cash = 0.0  # running cash flow from fills
        self._step = 0  # advances once per act() call

    def _active_side(self) -> Optional[Side]:
        for start, end, side in self.schedule:
            if start <= self._step < end:
                return side
        return None

    def _execute_market_order(self, book: LimitOrderBook, side: Side) -> None:
        """Send a market order and work out what it actually filled from the new trades."""
        start = len(book.trades)
        book.add_market_order(side, self.size)
        new_trades = book.trades[start:]

        filled = sum(size for _, size in new_trades)
        if filled == 0:
            return

        avg_price = sum(price * size for price, size in new_trades) / filled

        if side == "buy":
            self.inventory += filled
            self.cash -= filled * avg_price
        else:
            self.inventory -= filled
            self.cash += filled * avg_price

    def act(self, book: LimitOrderBook) -> None:
        """Trade in the active schedule window's direction, if any, then
        advance the internal step counter for the next call."""
        side = self._active_side()
        self._step += 1

        if side is None:
            return
        if side == "buy" and (self.max_inventory is None or self.inventory < self.max_inventory):
            self._execute_market_order(book, "buy")
        elif side == "sell" and (self.max_inventory is None or self.inventory > -self.max_inventory):
            self._execute_market_order(book, "sell")

    def mark_to_market(self, book: LimitOrderBook) -> float:
        """Cash plus the value of current inventory at the current mid price."""
        mid = book.mid_price() or 0
        return self.cash + self.inventory * mid
