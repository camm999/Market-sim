# tests/test_informed_trader.py
"""Unit tests for simulator.informed_trader.InformedTrader."""

import contextlib
import io

from lob.book import LimitOrderBook, Order
from simulator.informed_trader import InformedTrader
from simulator.market_maker import MarketMaker
from simulator.random_flow import simulate_random_flow


def make_book():
    return LimitOrderBook()


def test_no_trade_before_scheduled_window():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 20))

    trader = InformedTrader(schedule=[(2, 4, "buy")], size=5)
    trader.act(book)  # step 0
    trader.act(book)  # step 1

    assert trader.inventory == 0
    assert book.trades == []


def test_buys_during_active_buy_window():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 20))  # ask liquidity to trade against

    trader = InformedTrader(schedule=[(0, 2, "buy")], size=5)
    trader.act(book)  # step 0, inside the window

    assert trader.inventory == 5
    assert trader.cash == -5 * 101


def test_sells_during_active_sell_window():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 20))  # bid liquidity to trade against

    trader = InformedTrader(schedule=[(0, 1, "sell")], size=5)
    trader.act(book)  # step 0, inside the window

    assert trader.inventory == -5
    assert trader.cash == 5 * 99


def test_stops_trading_once_window_ends():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 20))

    trader = InformedTrader(schedule=[(0, 1, "buy")], size=5)  # window covers step 0 only
    trader.act(book)  # step 0: inside the window
    trades_after_first = len(book.trades)

    trader.act(book)  # step 1: window has ended

    assert trader.inventory == 5
    assert len(book.trades) == trades_after_first


def test_stops_trading_once_max_inventory_hit_when_capped():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 100))

    trader = InformedTrader(schedule=[(0, 5, "buy")], size=5, max_inventory=5)
    trader.act(book)  # step 0: inventory hits the cap of 5
    trades_after_first = len(book.trades)

    trader.act(book)  # step 1: still in-window, but blocked by max_inventory

    assert trader.inventory == 5
    assert len(book.trades) == trades_after_first


def test_uncapped_by_default_can_exceed_typical_risk_limits():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 1000))

    trader = InformedTrader(schedule=[(0, 15, "buy")], size=5)  # max_inventory defaults to None
    for _ in range(15):
        trader.act(book)

    assert trader.inventory == 75  # exceeds the 50-unit cap other agents default to
    assert trader.cash == -75 * 101


def test_mark_to_market_matches_cash_plus_inventory_at_mid():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 20))

    trader = InformedTrader(schedule=[(0, 1, "buy")], size=5)
    trader.act(book)

    other_book = make_book()
    other_book.add_limit_order(Order(500, "buy", 89, 1))
    other_book.add_limit_order(Order(501, "sell", 91, 1))  # mid = 90

    assert trader.mark_to_market(other_book) == trader.cash + trader.inventory * 90


def test_step_counter_advances_across_multiple_windows():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 20))
    book.add_limit_order(Order(2, "buy", 99, 20))

    trader = InformedTrader(schedule=[(0, 1, "buy"), (2, 3, "sell")], size=5)
    trader.act(book)  # step 0: buy window
    trader.act(book)  # step 1: gap, no window active
    trader.act(book)  # step 2: sell window

    assert trader.inventory == 0  # bought 5, then sold 5 back
    assert len(book.trades) == 2


def test_wires_into_simulate_random_flow():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    informed = InformedTrader(schedule=[(0, 5, "buy")], size=4)

    with contextlib.redirect_stdout(io.StringIO()):  # simulate_random_flow prints progress; silence it here
        simulate_random_flow(book, steps=10, sleep=0, market_maker=mm, informed_trader=informed)

    assert informed.inventory > 0
