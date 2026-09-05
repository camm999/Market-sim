# tests/test_book.py
"""Unit tests for lob.book.LimitOrderBook — matching, priority, and cancellation."""

from lob.book import LimitOrderBook, Order


def make_book():
    return LimitOrderBook()


# ---- resting orders / best bid & ask ----


def test_non_marketable_limit_orders_rest_in_book():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))
    book.add_limit_order(Order(2, "sell", 101, 7))

    snap = book.snapshot()
    assert snap["best_bid"] == 99
    assert snap["best_ask"] == 101
    assert snap["bids"] == {99: 10}
    assert snap["asks"] == {101: 7}
    assert snap["trades"] == []


def test_best_bid_and_ask_track_multiple_price_levels():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))
    book.add_limit_order(Order(2, "buy", 100, 5))
    book.add_limit_order(Order(3, "sell", 102, 4))
    book.add_limit_order(Order(4, "sell", 101, 7))

    assert book._best_bid() == 100
    assert book._best_ask() == 101


# ---- best price heap (lazy-deletion correctness) ----


def test_best_bid_survives_out_of_order_inserts_and_removals():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 95, 5))
    book.add_limit_order(Order(2, "buy", 105, 5))
    book.add_limit_order(Order(3, "buy", 100, 5))
    assert book._best_bid() == 105

    book.cancel_order(2)  # remove the current best bid's whole price level
    assert book._best_bid() == 100

    book.cancel_order(3)
    assert book._best_bid() == 95

    book.cancel_order(1)
    assert book._best_bid() is None


def test_best_bid_correct_after_levels_matched_away():
    book = make_book()
    for order_id, price in enumerate([98, 102, 95, 110, 90], start=1):
        book.add_limit_order(Order(order_id, "buy", price, 5))
    assert book._best_bid() == 110

    book.add_market_order("sell", 5)  # sweeps the 110 level entirely
    assert book._best_bid() == 102

    book.add_market_order("sell", 5)  # sweeps the 102 level entirely
    assert book._best_bid() == 98


def test_best_ask_correct_after_price_level_emptied_and_reused():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 5))
    assert book._best_ask() == 101

    book.cancel_order(1)  # price level 101 is gone; its heap entry is now stale
    assert book._best_ask() is None

    book.add_limit_order(Order(2, "sell", 101, 3))  # a new order reuses the same price
    assert book._best_ask() == 101

    book.cancel_order(2)
    assert book._best_ask() is None


# ---- matching ----


def test_marketable_buy_matches_resting_ask_fully():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 5))
    book.add_limit_order(Order(2, "buy", 101, 5))

    assert book.trades == [(101, 5)]
    assert book.asks == {}
    assert book.bids == {}


def test_marketable_sell_matches_resting_bid_fully():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 100, 5))
    book.add_limit_order(Order(2, "sell", 100, 5))

    assert book.trades == [(100, 5)]
    assert book.bids == {}
    assert book.asks == {}


def test_partial_fill_leaves_remainder_resting():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 3))
    book.add_limit_order(Order(2, "buy", 101, 10))

    assert book.trades == [(101, 3)]
    snap = book.snapshot()
    assert snap["asks"] == {}
    assert snap["bids"] == {101: 7}  # unmatched remainder rests on the book


def test_incoming_order_trades_at_resting_price_not_its_own_limit():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 5))
    book.add_limit_order(Order(2, "buy", 105, 5))  # willing to pay more, but fills at 101

    assert book.trades == [(101, 5)]


def test_non_marketable_order_does_not_trade():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 5))
    book.add_limit_order(Order(2, "buy", 100, 5))  # below the ask

    assert book.trades == []
    assert book.snapshot()["bids"] == {100: 5}
    assert book.snapshot()["asks"] == {101: 5}


def test_price_time_priority_older_order_matches_first():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 5))  # older
    book.add_limit_order(Order(2, "sell", 101, 5))  # newer, same price

    book.add_limit_order(Order(3, "buy", 101, 5))

    assert book.trades == [(101, 5)]
    assert 1 not in book.order_index  # older order fully filled and removed
    assert 2 in book.order_index  # newer order untouched
    assert book.snapshot()["asks"] == {101: 5}


# ---- market orders ----


def test_market_buy_sweeps_multiple_price_levels():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 5))
    book.add_limit_order(Order(2, "sell", 102, 5))

    book.add_market_order("buy", 8)

    assert book.trades == [(101, 5), (102, 3)]
    assert book.snapshot()["asks"] == {102: 2}


def test_market_sell_sweeps_multiple_price_levels():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 100, 5))
    book.add_limit_order(Order(2, "buy", 99, 5))

    book.add_market_order("sell", 8)

    assert book.trades == [(100, 5), (99, 3)]
    assert book.snapshot()["bids"] == {99: 2}


def test_market_order_with_insufficient_liquidity_does_not_crash():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 3))

    book.add_market_order("buy", 10)  # more size requested than available

    assert book.trades == [(101, 3)]
    assert book.asks == {}


# ---- cancellation ----


def test_cancel_order_removes_resting_order():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))

    assert book.cancel_order(1) is True
    assert book.bids == {}
    assert 1 not in book.order_index


def test_cancel_order_leaves_other_orders_at_same_price_level():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))
    book.add_limit_order(Order(2, "buy", 99, 5))

    book.cancel_order(1)

    assert book.snapshot()["bids"] == {99: 5}


def test_cancel_unknown_order_id_is_a_no_op(capsys):
    book = make_book()

    result = book.cancel_order(999)

    assert result is None
    assert "not found" in capsys.readouterr().out


# ---- mid price / spread ----


def test_mid_price_and_spread_with_both_sides():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))
    book.add_limit_order(Order(2, "sell", 101, 5))

    assert book.mid_price() == 100
    assert book.spread() == 2


def test_mid_price_with_only_bids_has_no_spread():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))

    assert book.mid_price() == 99
    assert book.spread() is None


def test_mid_price_with_only_asks_has_no_spread():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 5))

    assert book.mid_price() == 101
    assert book.spread() is None


def test_mid_price_defaults_to_100_when_book_never_had_a_price():
    book = make_book()
    assert book.mid_price() == 100


def test_mid_price_falls_back_to_last_known_mid_once_book_empties():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))
    book.add_limit_order(Order(2, "sell", 101, 5))
    book.mid_price()  # caches last_mid = 100

    book.add_market_order("buy", 5)  # clears the ask side
    book.cancel_order(1)  # clears the bid side too

    assert book.mid_price() == 100


# ---- index / depth invariants ----


def resting_orders(book):
    """every order object actually sitting on the book right now."""
    return [o for side in (book.bids, book.asks) for queue in side.values() for o in queue]


def assert_invariants(book):
    """order_index holds exactly the resting orders, and the cached depth totals agree
    with a full walk of the book. Both used to drift: fills reached by a market order,
    and limit orders fully filled on arrival, were left behind in order_index forever.
    """
    resting = resting_orders(book)
    assert set(book.order_index) == {o.id for o in resting}
    assert book.bid_depth() == sum(sum(o.size for o in q) for q in book.bids.values())
    assert book.ask_depth() == sum(sum(o.size for o in q) for q in book.asks.values())


def test_order_index_drops_orders_consumed_by_a_market_order():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 5))
    book.add_market_order("buy", 5)

    assert book.asks == {}
    assert_invariants(book)


def test_order_index_drops_a_limit_order_fully_filled_on_arrival():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 5))
    book.add_limit_order(Order(2, "buy", 101, 5))  # crosses and fills completely, never rests

    assert_invariants(book)


def test_cancelling_an_already_filled_order_reports_it_as_gone():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 5))
    book.add_market_order("buy", 5)

    assert book.cancel_order(1) is None  # not "False" from a half-present index entry


def test_partially_filled_order_stays_indexed_with_its_remaining_size():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 10))
    book.add_market_order("buy", 4)

    assert 1 in book.order_index
    assert book.ask_depth() == 6
    assert_invariants(book)


def test_invariants_hold_across_a_long_mixed_run():
    """the leak only showed up in aggregate, so drive a few thousand mixed operations."""
    import random

    rng = random.Random(11)
    book = make_book()
    live = []

    for order_id in range(1, 2001):
        roll = rng.random()
        if roll < 0.6:
            side = rng.choice(["buy", "sell"])
            order = Order(order_id, side, 100 + rng.randint(-4, 4), rng.randint(1, 10))
            book.add_limit_order(order)
            live.append(order_id)
        elif roll < 0.85:
            book.add_market_order(rng.choice(["buy", "sell"]), rng.randint(1, 10))
        elif live:
            book.cancel_order(live.pop(rng.randrange(len(live))))

    assert_invariants(book)
    assert len(book.order_index) < 2000  # i.e. it isn't just accumulating everything


def test_heaps_do_not_grow_without_bound():
    """lazy deletion leaves stale prices behind, so the heaps get compacted."""
    book = make_book()
    for order_id in range(1, 1001):
        price = 100 + (order_id % 40)
        book.add_limit_order(Order(order_id, "buy", price, 5))
        book.cancel_order(order_id)  # empties the level again, leaving a stale heap entry

    assert len(book._bid_heap) <= 2 * len(book.bids) + book._HEAP_COMPACT_SLACK + 1


# ---- depth and imbalance ----


def test_imbalance_is_signed_toward_the_heavier_side():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 30))
    book.add_limit_order(Order(2, "sell", 101, 10))

    assert book.imbalance() == (30 - 10) / 40


def test_imbalance_is_zero_on_an_empty_book():
    assert make_book().imbalance() == 0.0


def test_depth_can_be_limited_to_the_best_levels():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))  # best bid
    book.add_limit_order(Order(2, "buy", 98, 5))
    book.add_limit_order(Order(3, "buy", 50, 100))  # far from the touch, never going to trade
    book.add_limit_order(Order(4, "sell", 101, 10))

    assert book.bid_depth() == 115  # whole book
    assert book.bid_depth(levels=2) == 15  # two best levels only
    assert book.imbalance(levels=2) == (15 - 10) / 25
