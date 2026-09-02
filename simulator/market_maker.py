# simulator/market_maker.py

import statistics
from typing import List, Optional, Tuple

from lob.book import LimitOrderBook, Order


class MarketMaker:
    """
    simple two-sided market maker

    each step settles fills on last step's resting quotes, cancels
    what's left of them, then posts a fresh bid/ask straddling the mid.
    
    quoted width widens with recent realized volatility (`vol_coef`)
    and skews against inventory (`skew_coef`) to lean back toward flat.

    P&L splits into `spread_pnl` (edge captured per fill vs. the mid it
    was quoted around) and `inventory_pnl()` (mark-to-market swing on
    the carried position since then), shows whether P&L
    came from earning the spread or from getting picked off by
    flow and riding the position.
    """

    def __init__(
        self,
        order_id_start: int = 1_000_000,
        spread: float = 2,
        size: int = 5,
        max_inventory: int = 50,
        vol_window: int = 20,
        vol_coef: float = 1.0,
        skew_coef: float = 1.0,
    ) -> None:
        self.next_order_id = order_id_start
        self.spread = spread  # base quoted width around mid, before volatility widening
        self.size = size  # size posted on each side
        self.max_inventory = max_inventory  # risk limit before a side stops quoting
        self.vol_window = vol_window  # how many recent trades realized volatility looks back over
        self.vol_coef = vol_coef  # spread added per unit of realized volatility
        self.skew_coef = skew_coef  # multiplier on inventory-based quote skew; 0 disables it

        self.inventory = 0  # net position: +long, -short
        self.cash = 0.0  # running cash flow from fills
        self.spread_pnl = 0.0  # cumulative edge captured vs. mid at each fill's quote time

        self.bid_order: Optional[Order] = None
        self.bid_posted_size = 0
        self.bid_ref_mid: Optional[float] = None  # mid this bid was quoted around, for spread_pnl
        self.ask_order: Optional[Order] = None
        self.ask_posted_size = 0
        self.ask_ref_mid: Optional[float] = None

    def _new_id(self) -> int:
        order_id = self.next_order_id
        self.next_order_id += 1
        return order_id

    def _apply_fill(self, filled: int, price: float, is_buy: bool, ref_mid: float) -> None:
        if filled <= 0:  
            return
        if is_buy:
            self.inventory += filled  
            self.cash -= filled * price
            self.spread_pnl += filled * (ref_mid - price)  
        else:
            self.inventory -= filled
            self.cash += filled * price  # inc cash
            self.spread_pnl += filled * (price - ref_mid)

    def _apply_fills_from_trades(
        self, trades: List[Tuple[float, int]], is_buy: bool, ref_mid: float
    ) -> None:
        """Book fills at the price they actually traded at, not our own quote."""
        for price, size in trades:
            self._apply_fill(size, price, is_buy, ref_mid)

    def _realized_volatility(self, book: LimitOrderBook) -> float:
        """Population stdev of the last `vol_window` trade prices, 0 with fewer than 2."""
        recent_prices = [price for price, _ in book.trades[-self.vol_window :]]
        if len(recent_prices) < 2:
            return 0.0
        return statistics.pstdev(recent_prices)

    def _compute_quote_prices(self, book: LimitOrderBook, mid: float) -> Tuple[int, int]:
        """bid/ask around mid, base spread widened by recent volatility, then
        skewed against inventory"""
        volatility = self._realized_volatility(book)
        effective_spread = self.spread + self.vol_coef * volatility
        half = effective_spread / 2
        # (skew) positive inventory nudges both quotes down so we sell rather than buy more.
        skew = self.skew_coef * (self.inventory / self.max_inventory) * half if self.max_inventory else 0
        return round(mid - half - skew), round(mid + half - skew)

    def mark_to_market(self, book: LimitOrderBook) -> float:
        """cash plus the value of current inventory at the current mid price."""
        mid = book.mid_price() or 0
        return self.cash + self.inventory * mid  # position value at mid price

    def inventory_pnl(self, book: LimitOrderBook) -> float:
        """satisfies spread_pnl + inventory_pnl(book) == mark_to_market(book)."""
        return self.mark_to_market(book) - self.spread_pnl

    def quote(self, book: LimitOrderBook) -> None:
        """settle fills, cancel stale quotes, and post fresh ones around mid."""

        # Book whatever filled on last step's resting orders since they were posted,
        # crediting spread_pnl against the mid those orders were quoted around.
        if self.bid_order is not None:
            filled = self.bid_posted_size - self.bid_order.size
            assert self.bid_ref_mid is not None  # set whenever bid_order was posted
            self._apply_fill(filled, self.bid_order.price, is_buy=True, ref_mid=self.bid_ref_mid)
        if self.ask_order is not None:
            filled = self.ask_posted_size - self.ask_order.size
            assert self.ask_ref_mid is not None
            self._apply_fill(filled, self.ask_order.price, is_buy=False, ref_mid=self.ask_ref_mid)

        if self.bid_order is not None and self.bid_order.size > 0:  # cancels unfilled orders
            book.cancel_order(self.bid_order.id)
        if self.ask_order is not None and self.ask_order.size > 0:
            book.cancel_order(self.ask_order.id)

        self.bid_order = None
        self.ask_order = None

        mid = book.mid_price()
        if mid is None:
            return

        bid_price, ask_price = self._compute_quote_prices(book, mid)

        if self.inventory < self.max_inventory:
            order = Order(self._new_id(), "buy", bid_price, self.size)
            trades_before = len(book.trades)
            book.add_limit_order(order)
            self._apply_fills_from_trades(book.trades[trades_before:], is_buy=True, ref_mid=mid)
            self.bid_ref_mid = mid  # this order (filled or resting) was quoted around this mid
            if order.size > 0:
                self.bid_order = order
                self.bid_posted_size = order.size

        if self.inventory > -self.max_inventory:
            order = Order(self._new_id(), "sell", ask_price, self.size)
            trades_before = len(book.trades)
            book.add_limit_order(order)
            self._apply_fills_from_trades(book.trades[trades_before:], is_buy=False, ref_mid=mid)
            self.ask_ref_mid = mid
            if order.size > 0:
                self.ask_order = order
                self.ask_posted_size = order.size
