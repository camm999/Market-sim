# lob/book.py

from collections import deque
import heapq
from typing import Any, Deque, Dict, List, Literal, Optional, Tuple

Side = Literal["buy", "sell"]

DEFAULT_FALLBACK_MID = 100.0  # mid reported by a book that has never had a price


class Order:  # container for single order
    def __init__(self, order_id: int, side: Side, price: float, size: int) -> None:

        self.id = order_id
        self.side = side  # "buy" or "sell"
        self.price = price
        self.size = size


class LimitOrderBook:
    # lazy deletion (see _best_bid) leaves stale prices in the heaps, so they only ever
    # grow. Rebuild a heap once it holds more than this multiple of the live price
    # levels, with a small slack so tiny books don't thrash.
    _HEAP_COMPACT_RATIO = 2
    _HEAP_COMPACT_SLACK = 8

    def __init__(self, fallback_mid: float = DEFAULT_FALLBACK_MID) -> None:
        self.bids: Dict[float, Deque[Order]] = {}  # price → queue of buy orders
        self.asks: Dict[float, Deque[Order]] = {}  # price → queue of sell orders
        self.trades: List[Tuple[float, int]] = []  # list of (price, size)
        self.order_index: Dict[int, Tuple[Side, float, Order]] = (
            {}
        )  # order_id -> (side, price, order_object); holds exactly the orders currently resting
        self.last_mid: Optional[float] = (
            None  # cached mid price, used as a fallback once the book empties out
        )
        self.fallback_mid = fallback_mid  # mid reported before the book has ever had a price

        # heaps - see read_me and benchmarks/bench_best_price.py for why we use heaps to track best bid/ask
        self._bid_heap: List[float] = []
        self._ask_heap: List[float] = []

        # running totals of resting size per side. summing the whole book is O(total resting
        # orders), and both Metrics.update and ImbalanceTrader used to do exactly that every
        # step; keeping the totals in step with each add/fill/cancel makes those lookups O(1).
        self._bid_depth = 0
        self._ask_depth = 0

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

    def _rest_bid(self, order: Order) -> None:
        """park the unfilled remainder of a buy order at its price level."""
        queue = self.bids.get(order.price)
        if queue is None:
            # index the new level *before* it exists in self.bids, so a compaction here
            # can't rebuild the heap with this price already in it and then double-push it
            if len(self._bid_heap) > self._HEAP_COMPACT_RATIO * len(self.bids) + self._HEAP_COMPACT_SLACK:
                self._bid_heap = [-p for p in self.bids]
                heapq.heapify(self._bid_heap)
            heapq.heappush(self._bid_heap, -order.price)  # new price level: index it
            queue = self.bids[order.price] = deque()
        queue.append(order)  # queues are FIFO, so appending preserves time priority
        self._bid_depth += order.size

    def _rest_ask(self, order: Order) -> None:
        """park the unfilled remainder of a sell order at its price level."""
        queue = self.asks.get(order.price)
        if queue is None:
            if len(self._ask_heap) > self._HEAP_COMPACT_RATIO * len(self.asks) + self._HEAP_COMPACT_SLACK:
                self._ask_heap = list(self.asks)
                heapq.heapify(self._ask_heap)
            heapq.heappush(self._ask_heap, order.price)  # new price level: index it
            queue = self.asks[order.price] = deque()
        queue.append(order)
        self._ask_depth += order.size

    def add_limit_order(self, order: Order) -> None:
        """add a limit order to the book or match it if marketable."""
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
            self._ask_depth -= trade_size

            self.trades.append((best_ask, trade_size))  # Record the trade

            if best_order.size == 0:  ##If the resting order is fully filled
                del self.order_index[best_order.id]
                ask_queue.popleft()  # Remove it from the queue. (popleft removes furthest left el)
                if not ask_queue:  # If the queue is empty, remove the entire price level.
                    del self.asks[best_ask]

        # If remaining size, add to book
        if order.size > 0:
            self._rest_bid(order)
        else:
            # fully filled on arrival: it never rests, so it must not stay indexed
            del self.order_index[order.id]

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
            self._bid_depth -= trade_size

            self.trades.append((best_bid, trade_size))

            if best_order.size == 0:
                del self.order_index[best_order.id]
                bid_queue.popleft()
                if not bid_queue:
                    del self.bids[best_bid]

        # If remaining size, add to book
        if order.size > 0:
            self._rest_ask(order)
        else:
            del self.order_index[order.id]

    def bid_depth(self, levels: Optional[int] = None) -> int:
        """total resting buy size. the default (whole book) is O(1) off a running
        total; `levels=n` sums only the n best price levels instead, which is what
        depth and imbalance actually mean in a real market - orders far from the
        touch are never going to trade."""
        if levels is None:
            return self._bid_depth
        return sum(o.size for p in heapq.nlargest(levels, self.bids) for o in self.bids[p])

    def ask_depth(self, levels: Optional[int] = None) -> int:
        """total resting sell size; see bid_depth."""
        if levels is None:
            return self._ask_depth
        return sum(o.size for p in heapq.nsmallest(levels, self.asks) for o in self.asks[p])

    def imbalance(self, levels: Optional[int] = None) -> float:
        """(bid - ask) / (bid + ask) resting size, in [-1, 1]; 0 on an empty book."""
        bid_depth = self.bid_depth(levels)
        ask_depth = self.ask_depth(levels)
        total = bid_depth + ask_depth
        if total == 0:
            return 0.0
        return (bid_depth - ask_depth) / total

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
        """market buy, hit best asks until size is gone or no asks remain."""
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
            self._ask_depth -= trade_size

            self.trades.append((best_ask, trade_size))

            if best_order.size == 0:
                del self.order_index[best_order.id]
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
            self._bid_depth -= trade_size

            self.trades.append((best_bid, trade_size))

            if best_order.size == 0:
                del self.order_index[best_order.id]
                bid_queue.popleft()
                if not bid_queue:
                    del self.bids[best_bid]

    def cancel_order(self, order_id: int) -> Optional[bool]:
        """cancel an existing resting order by ID."""
        if order_id not in self.order_index:
            print("order not found or already filled")
            return None

        side, price, _order = self.order_index[order_id]
        del self.order_index[order_id]  # the index holds resting orders only, so drop it either way

        # Select correct book side
        book = self.bids if side == "buy" else self.asks

        if price not in book:
            return False  # price level disappeared (should not happen)

        queue = book[price]

        # Remove the order object from the queue
        for o in queue:  # scan through queue and remove it
            if o.id == order_id:
                queue.remove(o)
                if side == "buy":
                    self._bid_depth -= o.size  # o.size is what's *left* of a partially filled order
                else:
                    self._ask_depth -= o.size
                break
        else:
            return False  # indexed but not actually resting (should not happen)

        # Clean up empty price level
        if not queue:
            del book[price]  # if price level empty, remove it

        return True

    # add mid,spread metricsfor random flow, very simple

    def mid_price(self) -> float:
        best_bid = self._best_bid() if self.bids else None
        best_ask = self._best_ask() if self.asks else None

        # if both sides exist → normal mid
        if best_bid is not None and best_ask is not None:
            mid = (best_bid + best_ask) / 2
            self.last_mid = mid
            return mid

        # if only one side exists → use that as mid
        if best_bid is not None:
            self.last_mid = best_bid
            return best_bid

        if best_ask is not None:
            self.last_mid = best_ask
            return best_ask

        # if book empty → fallback to last mid, or the configured starting mid
        if self.last_mid is not None:
            return self.last_mid

        return self.fallback_mid

    def spread(self) -> Optional[float]:
        best_bid = self._best_bid()
        best_ask = self._best_ask()
        if best_bid is not None and best_ask is not None:
            return best_ask - best_bid
        return None
