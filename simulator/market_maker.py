# simulator/market_maker.py

from lob.book import Order


class MarketMaker:
    """
    A simple two-sided market maker.

    Each step it settles fills on last step's resting quotes, cancels
    whatever's left of them, then posts a fresh bid and ask straddling the
    mid price. It earns the spread on round trips, but every fill also
    moves its inventory — so quotes are skewed against that inventory
    (long -> quote lower, short -> quote higher) to lean back towards flat
    instead of letting risk build up unbounded.
    """

    def __init__(self, order_id_start=1_000_000, spread=2, size=5, max_inventory=50):
        self.next_order_id = order_id_start
        self.spread = spread              # full quoted width around mid
        self.size = size                  # size posted on each side
        self.max_inventory = max_inventory  # risk limit before a side stops quoting

        self.inventory = 0    # net position: +long, -short
        self.cash = 0.0       # running cash flow from fills

        self.bid_order = None
        self.bid_posted_size = 0
        self.ask_order = None
        self.ask_posted_size = 0

    def _new_id(self):
        order_id = self.next_order_id
        self.next_order_id += 1
        return order_id

    def _apply_fill(self, filled, price, is_buy):
        if filled <= 0:    #no fill
            return
        if is_buy:
            self.inventory += filled   #dec cash
            self.cash -= filled * price
        else:
            self.inventory -= filled
            self.cash += filled * price   #inc cash

    def mark_to_market(self, book):
        """Cash plus the value of current inventory at the current mid price."""
        mid = book.mid_price() or 0
        return self.cash + self.inventory * mid   #position value at mid price

    def quote(self, book):
        """Settle fills, cancel stale quotes, and post fresh ones around mid."""

        # Book whatever filled on last step's resting orders since they were posted.
        if self.bid_order is not None:
            filled = self.bid_posted_size - self.bid_order.size
            self._apply_fill(filled, self.bid_order.price, is_buy=True)
        if self.ask_order is not None:
            filled = self.ask_posted_size - self.ask_order.size
            self._apply_fill(filled, self.ask_order.price, is_buy=False)

        if self.bid_order is not None and self.bid_order.size > 0:   #cancels unfilled orders
            book.cancel_order(self.bid_order.id)
        if self.ask_order is not None and self.ask_order.size > 0:
            book.cancel_order(self.ask_order.id)  

        self.bid_order = None
        self.ask_order = None

        mid = book.mid_price()
        if mid is None:
            return

        half = self.spread / 2
        # Skew: positive inventory nudges both quotes down so we sell rather than buy more.
        skew = (self.inventory / self.max_inventory) * half if self.max_inventory else 0
        bid_price = round(mid - half - skew)
        ask_price = round(mid + half - skew)

        if self.inventory < self.max_inventory:
            order = Order(self._new_id(), "buy", bid_price, self.size)
            posted_size = order.size
            book.add_limit_order(order)
            self._apply_fill(posted_size - order.size, bid_price, is_buy=True)
            if order.size > 0:
                self.bid_order = order
                self.bid_posted_size = order.size

        if self.inventory > -self.max_inventory:
            order = Order(self._new_id(), "sell", ask_price, self.size)
            posted_size = order.size
            book.add_limit_order(order)
            self._apply_fill(posted_size - order.size, ask_price, is_buy=False)
            if order.size > 0:
                self.ask_order = order
                self.ask_posted_size = order.size
