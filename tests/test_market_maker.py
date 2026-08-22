# tests/test_market_maker.py
"""Unit tests for simulator.market_maker.MarketMaker."""

from lob.book import LimitOrderBook, Order
from simulator.market_maker import MarketMaker


def make_book():
    return LimitOrderBook()


def test_quote_posts_bid_and_ask_around_mid_on_empty_book():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)

    mm.quote(book)

    snap = book.snapshot()
    assert snap["bids"] == {99: 5}  # empty book falls back to mid=100, half-spread=1
    assert snap["asks"] == {101: 5}
    assert mm.inventory == 0
    assert mm.cash == 0.0


def test_quote_replaces_stale_quotes_next_step():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)

    mm.quote(book)
    first_bid_id = mm.bid_order.id
    first_ask_id = mm.ask_order.id

    mm.quote(book)  # nothing traded in between, should cancel + repost fresh orders

    assert book.snapshot()["bids"] == {99: 5}
    assert book.snapshot()["asks"] == {101: 5}
    assert mm.bid_order.id != first_bid_id
    assert mm.ask_order.id != first_ask_id


def test_immediate_fill_on_post_when_pinned_short_and_book_is_ask_only():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 100, 3))  # only an ask resting, no bid

    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    mm.inventory = -50  # pinned at the short cap: skew pushes bid_price up to exactly mid (100)

    mm.quote(book)  # bid_price == best_ask == 100, so it crosses immediately

    assert mm.inventory == -47  # bought back 3 of the 50 it was short
    assert mm.cash == -3 * 100
    assert mm.bid_order.size == 2  # remaining unfilled size rests in the book
    assert mm.ask_order.size == 5  # inventory (-47) is back above the cap, so ask still posts


def test_settles_fill_that_happened_between_quote_calls():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    mm.quote(book)  # posts bid 99x5, ask 101x5

    book.add_market_order("buy", 5)  # something else sweeps the market maker's ask

    mm.quote(book)  # should notice the ask filled before cancelling/reposting

    assert mm.inventory == -5
    assert mm.cash == 5 * 101


def test_quotes_skew_against_inventory():
    book = make_book()
    mm = MarketMaker(spread=4, size=5, max_inventory=50)
    mm.inventory = 25  # already long, halfway to the risk limit

    mm.quote(book)

    # skew = (25/50) * (4/2) = 1, mid falls back to 100 on an empty book
    assert book.snapshot()["bids"] == {97: 5}
    assert book.snapshot()["asks"] == {101: 5}


def test_stops_quoting_bid_side_once_max_inventory_reached():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    mm.inventory = 50

    mm.quote(book)

    assert mm.bid_order is None
    assert mm.ask_order is not None
    assert book.snapshot()["bids"] == {}


def test_stops_quoting_ask_side_once_max_inventory_reached_short():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    mm.inventory = -50

    mm.quote(book)

    assert mm.ask_order is None
    assert mm.bid_order is not None
    assert book.snapshot()["asks"] == {}
