# tests/test_imbalance_trader.py
"""Unit tests for simulator.imbalance_trader.ImbalanceTrader."""

from lob.book import LimitOrderBook, Order
from simulator.imbalance_trader import ImbalanceTrader


def make_book():
    return LimitOrderBook()


def test_no_trade_when_book_is_balanced():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))
    book.add_limit_order(Order(2, "sell", 101, 10))

    trader = ImbalanceTrader(threshold=0.4, size=5)
    trader.act(book)

    assert trader.inventory == 0
    assert book.trades == []


def test_buys_when_bid_side_is_heavily_stacked():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 40))
    book.add_limit_order(Order(2, "sell", 101, 5))  # thin ask side to trade against

    trader = ImbalanceTrader(threshold=0.4, size=5)
    trader.act(book)

    assert trader.inventory == 5
    assert trader.cash == -5 * 101


def test_sells_when_ask_side_is_heavily_stacked():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 40))
    book.add_limit_order(Order(2, "buy", 99, 5))  # thin bid side to trade against

    trader = ImbalanceTrader(threshold=0.4, size=5)
    trader.act(book)

    assert trader.inventory == -5
    assert trader.cash == 5 * 99


def test_stops_trading_once_max_inventory_hit():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 40))
    book.add_limit_order(Order(2, "sell", 101, 10))

    trader = ImbalanceTrader(threshold=0.4, size=5, max_inventory=5)
    trader.act(book)  # inventory hits 5, the cap
    trades_after_first = len(book.trades)

    trader.act(book)  # should now be blocked by max_inventory

    assert trader.inventory == 5
    assert len(book.trades) == trades_after_first
