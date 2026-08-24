# tests/test_depth_history.py
"""Unit tests for metrics.depth_history.DepthHistory."""

from lob.book import LimitOrderBook, Order
from metrics.depth_history import DepthHistory


def make_book():
    return LimitOrderBook()


def test_update_bins_bids_positive_and_asks_negative_by_offset_from_mid():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))  # mid = 100, offset -1
    book.add_limit_order(Order(2, "sell", 101, 7))  # offset +1

    history = DepthHistory(offset_range=5)
    history.update(book)

    frame = history.frames[0]
    center = history.offset_range
    assert frame[center - 1] == 10  # bid depth stored as positive
    assert frame[center + 1] == -7  # ask depth stored as negative
    assert frame[center] == 0  # nothing resting exactly at mid


def test_offsets_outside_range_are_dropped():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 50, 10))  # mid = 75, offset -25: out of range
    book.add_limit_order(Order(2, "sell", 100, 7))  # offset +25: out of range

    history = DepthHistory(offset_range=5)
    history.update(book)

    frame = history.frames[0]
    assert (frame == 0).all()


def test_multiple_orders_at_the_same_price_level_sum_together():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 4))
    book.add_limit_order(Order(2, "buy", 99, 6))  # same price level as order 1
    book.add_limit_order(Order(3, "sell", 101, 5))

    history = DepthHistory(offset_range=5)
    history.update(book)

    frame = history.frames[0]
    center = history.offset_range
    assert frame[center - 1] == 10  # 4 + 6 summed at the same offset


def test_update_appends_one_frame_per_call():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))
    book.add_limit_order(Order(2, "sell", 101, 7))

    history = DepthHistory()
    history.update(book)
    history.update(book)
    history.update(book)

    assert len(history.frames) == 3
