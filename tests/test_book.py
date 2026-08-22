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
    assert 2 in book.order_index      # newer order untouched
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
    book.cancel_order(1)             # clears the bid side too

    assert book.mid_price() == 100
