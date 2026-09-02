# simulator/avellaneda_stoikov.py

import math
import statistics
from typing import Tuple

from lob.book import LimitOrderBook
from simulator.market_maker import MarketMaker


class AvellanedaStoikovMarketMaker(MarketMaker):
    """
    See read me for a full explanation of the Avellaneda-Stoikov model.

        reservation = mid - inventory * gamma * sigma^2 * time_remaining

    it then quotes a spread around that reservation price (not around mid):

        spread = gamma * sigma^2 * time_remaining + (2 / gamma) * ln(1 + gamma / k)

    gamma ----- risk aversion: higher = more averse to carrying inventory
    k --------- order-arrival intensity decay: sets the spread floor at zero risk
    T --------- trading horizon, in steps
    sigma ----- standard deviation
    SEE "BUG FIX" in README for a correction to the original paper's formula for the spread.
    """

    def __init__(
        self,
        order_id_start: int = 1_000_000,
        size: int = 5,
        max_inventory: int = 50,
        vol_window: int = 20,
        gamma: float = 0.0001,
        k: float = 1.5,
        total_steps: int = 500,
        max_variance_term: float = 20.0,
    ) -> None:
        super().__init__(
            order_id_start=order_id_start,
            spread=0,
            size=size,
            max_inventory=max_inventory,
            vol_window=vol_window,
            vol_coef=0,
            skew_coef=0,
        )
        self.gamma = gamma  # risk aversion: higher = more averse to carrying inventory
        self.k = k  # order-arrival intensity decay: sets the spread floor at zero risk
        self.total_steps = total_steps  # T: trading horizon, in steps
        self.t = 0  # current step, advances once per quote() call
        self.max_variance_term = max_variance_term  # quote-sanity clamp, see class docstring

    def _price_increment_variance(self, book: LimitOrderBook) -> float:
        """population variance of consecutive diffs between the last
        `vol_window` trade prices, it is clamped later"""
        recent_prices = [price for price, _ in book.trades[-self.vol_window :]]
        if len(recent_prices) < 3:  # need >= 2 diffs
            return 0.0
        diffs = [b - a for a, b in zip(recent_prices, recent_prices[1:])]
        return statistics.pvariance(diffs)

    def _reservation_and_half_spread(self, book: LimitOrderBook, mid: float) -> Tuple[float, float]:
        """the models real-valued view: reservation price and half-spread,
        before rounding to postable integer quotes.
        split from quote computation, allows for easier plot."""
        sigma2 = self._price_increment_variance(book)
        time_remaining = max(self.total_steps - self.t, 0)
        self.t += 1

        variance_term = min(self.gamma * sigma2 * time_remaining, self.max_variance_term)
        floor_term = (2 / self.gamma) * math.log(1 + self.gamma / self.k)
        half = (variance_term + floor_term) / 2

        skew_shift = self.inventory * self.gamma * sigma2 * time_remaining
        skew_shift = max(-half, min(half, skew_shift))  # never push a quote through fair value
        reservation = mid - skew_shift

        return reservation, half

    def _compute_quote_prices(self, book: LimitOrderBook, mid: float) -> Tuple[int, int]:
        reservation, half = self._reservation_and_half_spread(book, mid)
        return round(reservation - half), round(reservation + half)
