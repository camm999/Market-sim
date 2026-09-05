# simulator/informed_trader.py

from typing import List, Optional, Tuple

from lob.book import LimitOrderBook, Side
from simulator.agent import MarketTakingAgent


class InformedTrader(MarketTakingAgent):
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
        super().__init__()
        self.schedule = schedule  # (start_step, end_step, side), end exclusive
        self.size = size  # market order size sent each active step
        self.max_inventory = max_inventory  # risk cap; None = uncapped

        self._step = 0  # advances once per act() call

    def _active_side(self) -> Optional[Side]:
        for start, end, side in self.schedule:
            if start <= self._step < end:
                return side
        return None

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
