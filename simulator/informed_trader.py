# simulator/informed_trader.py

from typing import List, Optional, Tuple

from lob.book import LimitOrderBook, Side


class InformedTrader:
    """
    Fed a ground-truth schedule of future price-drift windows at
    construction — the simplest possible stand-in for a short-term
    informational edge — and simply trades a market order in that
    direction every step a window is active. Its own order flow is what
    causes the drift: real informed flow moves prices precisely because
    it trades ahead of information the rest of the market doesn't have
    yet, so this isn't a hack, it's the mechanism.

    Tracks its own step count internally (incremented once per `act()`
    call) rather than taking a step argument, so its call signature
    matches ImbalanceTrader's `act(book)` and it plugs into
    simulate_random_flow the same way. This assumes `act()` is called
    exactly once per simulation step, in order — true of every agent in
    this codebase today.

    Unlike the other agents, `max_inventory` defaults to None (uncapped):
    risk-capping is a liquidity-provider concept, and an informed trader
    riding a confirmed signal window is expected to run its full size for
    the full window rather than stopping partway through it.
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
