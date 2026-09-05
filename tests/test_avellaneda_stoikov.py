# tests/test_avellaneda_stoikov.py
"""Unit tests for simulator.avellaneda_stoikov.AvellanedaStoikovMarketMaker."""

from lob.book import LimitOrderBook
from simulator.avellaneda_stoikov import AvellanedaStoikovMarketMaker


def make_book():
    return LimitOrderBook()


# Reused fixture: prices [100, 102, 99, 103] -> diffs [2, -3, 4] -> pvariance = 8.6667.
# Distinct from _realized_volatility's level-stdev on the same fixture (pstdev([100,102,99,103])
# ~= 1.479, so pstdev^2 ~= 2.19), proving _price_increment_variance is really using increments.
VOL_TRADES = [(100, 1), (102, 1), (99, 1), (103, 1)]


def test_price_increment_variance_matches_hand_computed_diffs():
    book = make_book()
    book.trades = VOL_TRADES
    mm = AvellanedaStoikovMarketMaker()

    assert mm._price_increment_variance(book) == 8.666666666666666


def test_price_increment_variance_is_zero_with_fewer_than_three_trades():
    book = make_book()
    book.trades = [(100, 1), (105, 1)]  # only one diff, not enough for a variance
    mm = AvellanedaStoikovMarketMaker()

    assert mm._price_increment_variance(book) == 0.0


def test_reservation_price_shifts_below_mid_when_long():
    book = make_book()
    book.trades = VOL_TRADES
    mm = AvellanedaStoikovMarketMaker(max_inventory=50)
    mm.inventory = 1  # small enough that skew stays well under half the spread, unclamped

    bid, ask = mm._compute_quote_prices(book, 100.0)

    # sigma2=8.6667, time_remaining=500 (t=0): skew=1*0.0001*8.6667*500=0.4333,
    # floor=(2/0.0001)*ln(1+0.0001/1.5)=1.3333, half=(0.4333+1.3333)/2=0.8833
    # reservation=100-0.4333=99.5667 -> bid=round(98.6834)=99, ask=round(100.45)=100
    assert (bid, ask) == (99, 100)


def test_reservation_price_shifts_above_mid_when_short():
    book = make_book()
    book.trades = VOL_TRADES
    mm = AvellanedaStoikovMarketMaker(max_inventory=50)
    mm.inventory = -1  # mirror image of the long case

    bid, ask = mm._compute_quote_prices(book, 100.0)

    assert (bid, ask) == (100, 101)


def test_quotes_symmetric_around_mid_with_zero_inventory_and_zero_volatility():
    book = make_book()
    book.trades = [(100, 1)]  # not enough trades for a variance estimate
    mm = AvellanedaStoikovMarketMaker()

    bid, ask = mm._compute_quote_prices(book, 100.0)

    # Pure k-driven floor: half = (2/gamma)*ln(1+gamma/k) / 2 ~= 0.6666
    assert (bid, ask) == (99, 101)


def test_inventory_skew_never_pushes_a_quote_through_fair_value():
    """At a large inventory the raw q*gamma*sigma^2*(T-t) skew would exceed the
    spread's own half-width; it must clamp to half instead of crossing mid,
    the same invariant MarketMaker's linear skew guarantees by construction."""
    book = make_book()
    book.trades = VOL_TRADES
    mm = AvellanedaStoikovMarketMaker(max_inventory=50)
    mm.inventory = 50  # pinned long at the cap

    bid, ask = mm._compute_quote_prices(book, 100.0)

    assert (bid, ask) == (98, 100)
    assert ask >= 100  # never crosses through fair value to the other side


def test_variance_term_is_capped_so_a_volatility_spike_cannot_blow_up_the_spread():
    book = make_book()
    book.trades = [(100, 1), (1000, 1), (100, 1), (1000, 1)]  # engineered huge sigma2 = 720000
    mm = AvellanedaStoikovMarketMaker(max_variance_term=20.0)

    bid, ask = mm._compute_quote_prices(book, 100.0)

    # half = (max_variance_term + floor) / 2 = (20 + 1.3333) / 2 = 10.6666
    assert (bid, ask) == (89, 111)


def test_time_remaining_shrinks_the_variance_driven_terms_toward_the_floor():
    book = make_book()
    book.trades = VOL_TRADES
    mm = AvellanedaStoikovMarketMaker(max_inventory=50, total_steps=500)
    mm.inventory = 1
    mm.t = 499  # one step left in the horizon

    bid, ask = mm._compute_quote_prices(book, 100.0)

    # time_remaining=1 makes the variance term negligible; quotes collapse
    # toward the same pure-floor spread as the zero-volatility case.
    assert (bid, ask) == (99, 101)


def test_time_remaining_clamps_at_zero_past_the_horizon():
    book = make_book()
    book.trades = VOL_TRADES
    mm = AvellanedaStoikovMarketMaker(max_inventory=50, total_steps=500)
    mm.inventory = 1
    mm.t = 600  # already past the configured horizon

    bid, ask = mm._compute_quote_prices(book, 100.0)

    assert (bid, ask) == (99, 101)  # identical to time_remaining=1: clamps, doesn't go negative


def test_t_advances_once_per_quote_call():
    book = make_book()
    mm = AvellanedaStoikovMarketMaker()

    assert mm.t == 0
    mm.quote(book)
    assert mm.t == 1
    mm.quote(book)
    assert mm.t == 2


def test_settles_fill_that_happened_between_quote_calls():
    """Inherited MarketMaker plumbing (unchanged by this subclass) still works."""
    book = make_book()
    mm = AvellanedaStoikovMarketMaker(size=5, max_inventory=50)
    mm.quote(book)

    book.add_market_order("buy", 5)  # sweeps the market maker's ask

    mm.quote(book)

    assert mm.inventory == -5
    assert mm.cash > 0


def test_stops_quoting_bid_side_once_max_inventory_reached():
    book = make_book()
    mm = AvellanedaStoikovMarketMaker(size=5, max_inventory=50)
    mm.inventory = 50

    mm.quote(book)

    assert mm.bid_order is None
    assert mm.ask_order is not None


def test_stops_quoting_ask_side_once_max_inventory_reached_short():
    book = make_book()
    mm = AvellanedaStoikovMarketMaker(size=5, max_inventory=50)
    mm.inventory = -50

    mm.quote(book)

    assert mm.ask_order is None
    assert mm.bid_order is not None


def test_spread_pnl_and_inventory_pnl_sum_to_mark_to_market():
    book = make_book()
    mm = AvellanedaStoikovMarketMaker(size=5, max_inventory=50)
    mm.quote(book)

    book.add_market_order("buy", 5)  # sweeps the market maker's ask
    mm.quote(book)  # settles the fill, spread_pnl becomes nonzero

    total = mm.mark_to_market(book)
    assert mm.spread_pnl + mm.inventory_pnl(book) == total
