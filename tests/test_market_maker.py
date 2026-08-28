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


def test_spread_widens_with_recent_trade_volatility():
    book = make_book()
    # Alternating trade prices give a nonzero stdev of 5 (population stdev of [95, 105] * 5).
    book.trades = [(95, 1), (105, 1), (95, 1), (105, 1)]

    mm = MarketMaker(spread=2, size=5, max_inventory=50, vol_coef=1.0)
    mm.quote(book)

    # half = (2 + 1.0 * 5) / 2 = 3.5, mid falls back to 100 on an empty book
    assert book.snapshot()["bids"] == {96: 5}  # round(100 - 3.5)
    assert book.snapshot()["asks"] == {104: 5}  # round(100 + 3.5)


def test_spread_stays_at_base_with_fewer_than_two_trades():
    book = make_book()
    book.trades = [(100, 1)]  # one trade: not enough to compute a stdev

    mm = MarketMaker(spread=2, size=5, max_inventory=50, vol_coef=1.0)
    mm.quote(book)

    assert book.snapshot()["bids"] == {99: 5}
    assert book.snapshot()["asks"] == {101: 5}


def test_volatility_widening_only_looks_at_the_recent_window():
    book = make_book()
    # A wild trade sits outside the 4-trade window; the recent trades are all flat.
    book.trades = [(1000, 1), (100, 1), (100, 1), (100, 1), (100, 1)]

    mm = MarketMaker(spread=2, size=5, max_inventory=50, vol_window=4, vol_coef=1.0)
    mm.quote(book)

    assert book.snapshot()["bids"] == {99: 5}
    assert book.snapshot()["asks"] == {101: 5}


def test_vol_coef_zero_disables_volatility_widening():
    book = make_book()
    book.trades = [(95, 1), (105, 1), (95, 1), (105, 1)]

    mm = MarketMaker(spread=2, size=5, max_inventory=50, vol_coef=0.0)
    mm.quote(book)

    assert book.snapshot()["bids"] == {99: 5}
    assert book.snapshot()["asks"] == {101: 5}


def test_spread_pnl_captures_edge_relative_to_quote_time_mid():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    mm.quote(book)  # empty book -> mid=100, posts bid 99x5, ask 101x5

    book.add_market_order("buy", 5)  # sweeps our ask @ 101
    mm.quote(book)  # settles: sold 5 @ 101, quoted around mid=100 -> edge = 1/unit

    assert mm.spread_pnl == 5.0  # 5 * (101 - 100)


def test_spread_pnl_is_zero_when_an_immediate_fill_crosses_at_exactly_mid():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 100, 3))  # only an ask resting, no bid

    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    mm.inventory = -50  # pinned short: skew pushes bid_price up to exactly mid (100)

    mm.quote(book)  # bid_price == best_ask == mid == 100: no edge captured

    assert mm.spread_pnl == 0.0


def test_spread_pnl_and_inventory_pnl_sum_to_mark_to_market():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    mm.quote(book)  # mid=100, posts bid 99x5, ask 101x5

    book.add_market_order("buy", 5)  # sweeps our ask @ 101
    mm.quote(book)  # settles the fill, spread_pnl becomes nonzero

    total = mm.mark_to_market(book)
    assert mm.spread_pnl + mm.inventory_pnl(book) == total


def test_inventory_pnl_reflects_price_moves_after_the_fill():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    mm.quote(book)  # mid=100, posts bid 99x5, ask 101x5

    book.add_market_order("buy", 5)  # sweeps our ask @ 101
    mm.quote(book)  # settles: sold 5 @ 101 (quote mid 100) -> spread_pnl = 5

    assert mm.spread_pnl == 5.0
    assert mm.inventory == -5
    assert mm.cash == 5 * 101

    # Check the identity against an independent book fixing mid=90, decoupled
    # from whatever mm has resting on `book` after reposting above.
    other_book = make_book()
    other_book.add_limit_order(Order(500, "buy", 89, 1))
    other_book.add_limit_order(Order(501, "sell", 91, 1))  # mid = 90

    total = mm.mark_to_market(other_book)
    assert total == mm.cash + mm.inventory * 90  # short 5, price fell -> gain
    assert mm.inventory_pnl(other_book) == total - mm.spread_pnl
    assert mm.spread_pnl + mm.inventory_pnl(other_book) == total
