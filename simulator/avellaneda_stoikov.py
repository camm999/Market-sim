# simulator/avellaneda_stoikov.py

import math
import statistics
from typing import Tuple

from lob.book import LimitOrderBook
from simulator.market_maker import MarketMaker


class AvellanedaStoikovMarketMaker(MarketMaker):
    """
    A market maker quoting from the Avellaneda-Stoikov (2008) optimal-quoting
    model, instead of `MarketMaker`'s hand-tuned linear vol/skew heuristic.

    Each step it computes a reservation price - the price it would be
    indifferent to trading at given its current inventory, risk aversion
    (`gamma`), the recent variance of price moves, and how much of the
    trading horizon (`total_steps`) remains:

        reservation = mid - inventory * gamma * sigma^2 * time_remaining

    and quotes a spread around that reservation price (not around mid):

        spread = gamma * sigma^2 * time_remaining + (2 / gamma) * ln(1 + gamma / k)

    The first term is the same inventory-risk driver as the reservation
    price; the second comes from `k`, how fast counterparty order-arrival
    likelihood falls off with distance from mid, and sets a floor the spread
    never shrinks below even at zero inventory and zero volatility. Both
    terms involving `time_remaining` shrink to zero as the horizon is
    reached, so quotes flatten toward pure microstructure width near the end
    of the run - a genuine time dimension the linear heuristic doesn't have.

    Reuses `MarketMaker`'s settle/cancel/repost loop and P&L accounting
    unchanged (`quote()`, `_apply_fill`, `mark_to_market`, `inventory_pnl`)
    by overriding only `_compute_quote_prices`. `spread_pnl`/`inventory_pnl`
    still measure edge against the true mid, not the reservation price, so
    they stay comparable against `MarketMaker`'s P&L split.

    Unlike the paper, which assumes an exogenous mid-price process the
    market maker is too small to influence, this sim's mid is largely
    whatever price the market maker itself is quoting - it's usually the
    top of book. That closes a feedback loop the model doesn't account
    for: a large inventory skew pushes a quote away from mid, that quote
    gets hit, the resulting trade is a large price jump, and that jump
    feeds straight into next step's variance estimate, pushing the skew
    even further next time.

    Two safeguards address this, confirmed empirically necessary (a normal,
    honestly-computed volatility uptick while inventory sits near its cap
    was enough to spiral into an exploding, nonsensical quote within a
    handful of steps without them):

    - `max_variance_term` caps how much the variance-driven part of the
      spread (`gamma * sigma^2 * time_remaining`) can grow in one step,
      so a single large trade can't make next step's variance estimate -
      and therefore next step's spread and skew - blow up further.
    - The inventory skew is clamped to at most half the (already-capped)
      spread, exactly the invariant `MarketMaker`'s own linear skew
      guarantees by construction: it can pull a quote all the way to
      fair value, but never push it through to the other side. Without
      this, a large inventory combined with even a modest, uncapped
      variance term could push the ask below mid (or the bid above it) -
      an obviously bad quote that gets hit immediately, which is exactly
      the trade that was destabilizing the variance estimate.

    Both are the same kind of sanity clamp real quoting engines layer on
    top of theoretically clean pricing models, not part of the textbook
    formula - see the README's "Limitations" section for the full story.
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
        """Population variance of consecutive diffs between the last
        `vol_window` trade prices - the sigma^2 the model's dS = sigma*dW
        assumption actually calls for, unlike a stdev of price levels.
        Deliberately unclamped: this is the honest estimate, the sanity
        clamp is applied downstream in `_compute_quote_prices`."""
        recent_prices = [price for price, _ in book.trades[-self.vol_window :]]
        if len(recent_prices) < 3:  # need >= 2 diffs
            return 0.0
        diffs = [b - a for a, b in zip(recent_prices, recent_prices[1:])]
        return statistics.pvariance(diffs)

    def _reservation_and_half_spread(self, book: LimitOrderBook, mid: float) -> Tuple[float, float]:
        """The model's real-valued view: reservation price and half-spread,
        before rounding to postable integer quotes. Split out from
        `_compute_quote_prices` so callers that want the underlying signal
        (e.g. plotting the horizon-decay effect) aren't stuck reading it back
        out of rounded integer prices, which is too coarse to show a trend."""
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
