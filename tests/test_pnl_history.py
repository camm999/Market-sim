# tests/test_pnl_history.py
"""Unit tests for metrics.pnl_history.PnLHistory."""

from lob.book import LimitOrderBook
from metrics.pnl_history import PnLHistory
from simulator.market_maker import MarketMaker


def make_book():
    return LimitOrderBook()


def test_update_records_spread_inventory_and_total_pnl_each_step():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    history = PnLHistory()

    mm.quote(book)  # mid=100, posts bid 99x5, ask 101x5
    history.update(mm, book)

    book.add_market_order("buy", 5)  # sweeps our ask @ 101
    mm.quote(book)  # settles: sold 5 @ 101 (quote mid 100) -> spread_pnl = 5
    history.update(mm, book)

    assert len(history.spread_pnl) == 2
    assert len(history.inventory_pnl) == 2
    assert len(history.total_pnl) == 2
    assert history.spread_pnl[1] == 5.0


def test_spread_plus_inventory_equals_total_at_every_recorded_step():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    history = PnLHistory()

    for _ in range(5):
        mm.quote(book)
        book.add_market_order("buy", 2)
        history.update(mm, book)

    for spread, inventory, total in zip(
        history.spread_pnl, history.inventory_pnl, history.total_pnl
    ):
        assert spread + inventory == total


def test_update_appends_one_frame_per_call():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    history = PnLHistory()

    mm.quote(book)
    history.update(mm, book)
    history.update(mm, book)
    history.update(mm, book)

    assert len(history.total_pnl) == 3
