# benchmarks/bench_best_price.py
"""
Compares the old approach (max()/min() over every price level) against
the heap-based lookup now used in LimitOrderBook._best_bid()/_best_ask(),
across a growing number of price levels.

Run: python benchmarks/bench_best_price.py
"""

import heapq
import random
import time


def bench_dict_max(n_levels: int, n_calls: int) -> float:
    """The old approach: O(n) scan over every price level on every call."""
    # Build a dict of n_levels random "prices" -> dummy value, same shape as
    # LimitOrderBook.bids. Values don't matter here, only the keys (prices).
    d = {float(p): 1 for p in random.sample(range(1, 1_000_000), n_levels)}

    start = time.perf_counter()
    for _ in range(n_calls):
        max(d.keys())  # O(n): has to look at every key to find the biggest one
    return time.perf_counter() - start  # total time for n_calls lookups


def bench_heap(n_levels: int, n_calls: int) -> float:
    """The new approach: O(1) peek at the top of a heap-based index."""
    d = {float(p): 1 for p in random.sample(range(1, 1_000_000), n_levels)}

    # Negate every price so a min-heap behaves like a max-heap (see book.py's
    # _bid_heap for the real version of this trick).
    heap = [-p for p in d]
    heapq.heapify(heap)  # O(n), but only paid once here, not once per lookup

    start = time.perf_counter()
    for _ in range(n_calls):
        # This loop is the same lazy-deletion logic as _best_bid()/_best_ask():
        # peek the top, and only pop if it's stale. In this benchmark nothing
        # is ever deleted from `d`, so the top is always valid and this loop
        # body runs exactly once per call -> O(1) in practice.
        while heap:
            price = -heap[0]  # O(1): just reading index 0, undoing the negation
            if price in d:  # O(1): dict membership check
                break  # top of heap is still a real price level - that's our answer
            heapq.heappop(heap)  # stale entry (would only happen after a deletion)
    return time.perf_counter() - start


if __name__ == "__main__":
    print(f"{'levels':>8}  {'dict max()':>12}  {'heap peek':>12}  {'speedup':>8}")
    for n in [10, 100, 1_000, 10_000, 50_000]:
        # Same n_levels and n_calls for both, so the only thing that differs
        # between the two timings is O(n) scan vs O(1) peek.
        t_dict = bench_dict_max(n, 5000)
        t_heap = bench_heap(n, 5000)
        print(f"{n:8d}  {t_dict * 1000:10.2f}ms  {t_heap * 1000:10.2f}ms  {t_dict / t_heap:7.1f}x")
