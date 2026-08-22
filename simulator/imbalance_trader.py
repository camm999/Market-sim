# simulator/imbalance_trader.py

from lob.book import LimitOrderBook, Side


class ImbalanceTrader:
    """
    A simple momentum trader that reacts to order book imbalance.

    Where MarketMaker leans its quotes AGAINST its own inventory to stay
    flat, this agent leans WITH the book's imbalance: when there's much
    more resting size on the bid than the ask, that pressure often
    precedes the price getting pushed up, so it hits the market with a
    buy to ride that move (and mirrors the logic on the sell side).
    """

    def __init__(self, threshold: float = 0.4, size: int = 5, max_inventory: int = 50) -> None:
        self.threshold = threshold  # imbalance magnitude required to act
        self.size = size  # market order size per trade
        self.max_inventory = max_inventory  # risk limit

        self.inventory = 0  # net position: +long, -short
        self.cash = 0.0  # running cash flow from fills

    def _imbalance(self, book: LimitOrderBook) -> float:
        bid_depth = sum(sum(o.size for o in q) for q in book.bids.values())
        ask_depth = sum(sum(o.size for o in q) for q in book.asks.values())
        total = bid_depth + ask_depth
        if total == 0:
            return 0
        return (bid_depth - ask_depth) / total

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
        """Check the book's imbalance and, if it's strong enough, trade with it."""
        imbalance = self._imbalance(book)

        if imbalance > self.threshold and self.inventory < self.max_inventory:
            self._execute_market_order(book, "buy")

        elif imbalance < -self.threshold and self.inventory > -self.max_inventory:
            self._execute_market_order(book, "sell")

    def mark_to_market(self, book: LimitOrderBook) -> float:
        """Cash plus the value of current inventory at the current mid price."""
        mid = book.mid_price() or 0
        return self.cash + self.inventory * mid
