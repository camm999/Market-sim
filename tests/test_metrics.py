# tests/test_metrics.py
"""Unit tests for metrics.metrics.Metrics."""

import matplotlib

matplotlib.use("Agg")  # no display in CI

from lob.book import LimitOrderBook, Order  # noqa: E402
from metrics.metrics import Metrics  # noqa: E402


def make_book():
    return LimitOrderBook()


def test_update_records_mid_and_spread():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))
    book.add_limit_order(Order(2, "sell", 101, 7))

    metrics = Metrics()
    metrics.update(book)

    assert metrics.mid_prices == [100]
    assert metrics.spreads == [2]


def test_spread_is_none_while_only_one_side_is_quoted():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))

    metrics = Metrics()
    metrics.update(book)

    assert metrics.spreads == [None]
    assert metrics.mid_prices == [99]  # falls back to the side that exists


def test_update_records_depth_per_side_and_total():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))
    book.add_limit_order(Order(2, "buy", 98, 4))
    book.add_limit_order(Order(3, "sell", 101, 7))

    metrics = Metrics()
    metrics.update(book)

    assert metrics.bid_depths == [14]
    assert metrics.ask_depths == [7]
    assert metrics.total_depths == [21]


def test_depth_tracks_fills_and_cancels():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 10))
    book.add_limit_order(Order(2, "buy", 99, 10))

    metrics = Metrics()
    metrics.update(book)
    book.add_market_order("buy", 4)  # eats 4 off the ask
    book.cancel_order(2)  # pulls the whole bid
    metrics.update(book)

    assert metrics.ask_depths == [10, 6]
    assert metrics.bid_depths == [10, 0]


def test_imbalance_is_signed_toward_the_heavier_side():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 30))
    book.add_limit_order(Order(2, "sell", 101, 10))

    metrics = Metrics()
    metrics.update(book)

    assert metrics.imbalances == [(30 - 10) / 40]


def test_imbalance_is_zero_on_an_empty_book():
    metrics = Metrics()
    metrics.update(make_book())

    assert metrics.imbalances == [0]
    assert metrics.total_depths == [0]


def test_update_appends_one_frame_per_call():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))
    book.add_limit_order(Order(2, "sell", 101, 7))

    metrics = Metrics()
    for _ in range(5):
        metrics.update(book)

    assert len(metrics.mid_prices) == 5
    assert len(metrics.spreads) == 5
    assert len(metrics.imbalances) == 5
    assert len(metrics.total_depths) == 5


def test_new_trades_are_recorded_once_each():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 10))

    metrics = Metrics()
    metrics.update(book)

    book.add_market_order("buy", 4)
    metrics.update(book)
    metrics.update(book)  # nothing new happened since the last call

    assert metrics.trade_prices == [101]
    assert metrics.trade_sizes == [4]


def test_trades_that_predate_the_first_update_are_still_picked_up():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 10))
    book.add_market_order("buy", 6)

    metrics = Metrics()
    metrics.update(book)

    assert metrics.trade_prices == [101]
    assert metrics.trade_sizes == [6]


def test_plot_writes_a_figure(tmp_path):
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))
    book.add_limit_order(Order(2, "sell", 101, 7))

    metrics = Metrics()
    for _ in range(3):
        metrics.update(book)

    save_path = tmp_path / "metrics.png"
    figure = metrics.plot(save_path=str(save_path))

    assert save_path.exists()
    assert len(figure.axes) == 3  # mid price, spread, imbalance
