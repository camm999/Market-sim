# lob/book.py

from collections import deque
import heapq
from typing import Any, Deque, Dict, List, Literal, Optional, Tuple

Side = Literal["buy", "sell"]


class Order:  # container for single order
    def __init__(self, order_id: int, side: Side, price: float, size: int) -> None:

        self.id = order_id
        self.side = side  # "buy" or "sell"
        self.price = price
        self.size = size


class LimitOrderBook:
    def __init__(self) -> None:
        self.bids: Dict[float, Deque[Order]] = {}  # price → queue of buy orders
        self.asks: Dict[float, Deque[Order]] = {}  # price → queue of sell orders
        self.trades: List[Tuple[float, int]] = []  # list of (price, size)
        self.order_index: Dict[int, Tuple[Side, float, Order]] = (
            {}
        )  # order_id -> (side, price, order_object)
        self.last_mid: Optional[float] = (
            None  # cached mid price, used as a fallback once the book empties out
        )

        # heaps - see read_me and benchmarks/bench_best_price.py for why we use heaps to track best bid/ask
        self._bid_heap: List[float] = []
        self._ask_heap: List[float] = []

    def _best_bid(self) -> Optional[float]:
        while self._bid_heap:
            price = -self._bid_heap[0]
            if price in self.bids:
                return price
            heapq.heappop(self._bid_heap)  # stale entry: that price level no longer exists
        return None

    def _best_ask(self) -> Optional[float]:
        while self._ask_heap:
            price = self._ask_heap[0]
            if price in self.asks:
                return price
            heapq.heappop(self._ask_heap)  # stale entry: that price level no longer exists
        return None

    def add_limit_order(self, order: Order) -> None:
        """Add a limit order to the book or match it if marketable."""
        self.order_index[order.id] = (
            order.side,
            order.price,
            order,
        )  # store index before match, then even partially filled can be cancelled
        if order.side == "buy":
            return self._match_buy(order)
        else:
            return self._match_sell(order)

    def _match_buy(self, order: Order) -> None:
        while order.size > 0 and self.asks:
            best_ask = self._best_ask()  # Identify the best ask
            assert (
                best_ask is not None
            )  # guaranteed by the `self.asks` check in the while condition
            if order.price < best_ask:  # Check if the buy order is marketable
                break  # not marketable
            # We loop while: The incoming order still has remaining size. There are asks in the book.
            # Get the queue of sell orders at the best ask
            ask_queue = self.asks[best_ask]  # FIFO queue, first in first out
            best_order = ask_queue[0]  # oldest one , both of these enforce price-time priority

            trade_size = min(order.size, best_order.size)  # ensure we never overfill order
            order.size -= trade_size  # reduce both sizes
            best_order.size -= trade_size

            self.trades.append((best_ask, trade_size))  # Record the trade

            if best_order.size == 0:  ##If the resting order is fully filled
                del self.order_index[best_order.id]
                ask_queue.popleft()  # Remove it from the queue. (popleft removes furthest left el)
                if not ask_queue:  # If the queue is empty, remove the entire price level.
                    del self.asks[best_ask]

        # If remaining size, add to book
        if order.size > 0:
            if order.price not in self.bids:
                heapq.heappush(self._bid_heap, -order.price)  # new price level: index it
            self.bids.setdefault(order.price, deque()).append(order)  # setdefault ensures a queue exists at that price. Append adds order to end of queue.

    def _match_sell(self, order: Order) -> None:
        while order.size > 0 and self.bids:
            best_bid = self._best_bid()
            assert (
                best_bid is not None
            )  # guaranteed by the `self.bids` check in the while condition
            if order.price > best_bid:
                break  # not marketable

            bid_queue = self.bids[best_bid]
            best_order = bid_queue[0]

            trade_size = min(order.size, best_order.size)
            order.size -= trade_size
            best_order.size -= trade_size

            self.trades.append((best_bid, trade_size))

            if best_order.size == 0:
                del self.order_index[best_order.id]
                bid_queue.popleft()
                if not bid_queue:
                    del self.bids[best_bid]

        # If remaining size, add to book
        if order.size > 0:
            if order.price not in self.asks:
                heapq.heappush(self._ask_heap, order.price)  # new price level: index it
            self.asks.setdefault(order.price, deque()).append(order)

    def snapshot(self) -> Dict[str, Any]:

        return {
            "best_bid": self._best_bid(),
            "best_ask": self._best_ask(),
            "bids": {p: sum(o.size for o in q) for p, q in self.bids.items()},
            "asks": {p: sum(o.size for o in q) for p, q in self.asks.items()},
            "trades": self.trades[-5:],
        }

    def add_market_order(self, side: Side, size: int) -> None:

        if side == "buy":
            return self._market_buy(size)

        # match best ask until size is gone
        else:
            return self._market_sell(size)

        # match until size is gone

    def _market_buy(self, size: int) -> None:
        """Market buy: hit best asks until size is gone or no asks remain."""
        while size > 0 and self.asks:
            best_ask = self._best_ask()
            assert (
                best_ask is not None
            )  # guaranteed by the `self.asks` check in the while condition
            ask_queue = self.asks[best_ask]
            best_order = ask_queue[0]

            trade_size = min(size, best_order.size)
            size -= trade_size
            best_order.size -= trade_size

            self.trades.append((best_ask, trade_size))

            if best_order.size == 0:
                ask_queue.popleft()
                if not ask_queue:
                    del self.asks[best_ask]

    def _market_sell(self, size: int) -> None:
        while size > 0 and self.bids:
            best_bid = self._best_bid()
            assert (
                best_bid is not None
            )  # guaranteed by the `self.bids` check in the while condition
            bid_queue = self.bids[best_bid]
            best_order = bid_queue[0]

            trade_size = min(size, best_order.size)
            size -= trade_size
            best_order.size -= trade_size

            self.trades.append((best_bid, trade_size))

            if best_order.size == 0:
                bid_queue.popleft()
                if not bid_queue:
                    del self.bids[best_bid]

    def cancel_order(self, order_id: int) -> Optional[bool]:
        """Cancel an existing resting order by ID."""
        if order_id not in self.order_index:
            print("order not found or already filled")
            return None

        side, price, order_obj = self.order_index[order_id]

        # Select correct book side
        book = self.bids if side == "buy" else self.asks

        if price not in book:
            return False  # price level disappeared (should not happen)

        queue = book[price]

        # Remove the order object from the queue
        for i, o in enumerate(queue):  # scan through queue and remove it
            if o.id == order_id:
                queue.remove(o)
                break

        # Clean up empty price level
        if not queue:
            del book[price]  # if price level empty, remove it

        # Remove from index
        del self.order_index[order_id]

        return True

    # add mid,spread metricsfor random flow, very simple

    def mid_price(self) -> float:
        best_bid = self._best_bid() if self.bids else None
        best_ask = self._best_ask() if self.asks else None

        # If both sides exist → normal mid
        if best_bid is not None and best_ask is not None:
            mid = (best_bid + best_ask) / 2
            self.last_mid = mid
            return mid

        # If only one side exists → use that as mid
        if best_bid is not None:
            self.last_mid = best_bid
            return best_bid

        if best_ask is not None:
            self.last_mid = best_ask
            return best_ask

        # If book is empty → fallback to last mid or 100
        if self.last_mid is not None:
            return self.last_mid

        return 100

    def spread(self) -> Optional[float]:
        best_bid = self._best_bid()
        best_ask = self._best_ask()
        if best_bid is not None and best_ask is not None:
            return best_ask - best_bid
        return None
