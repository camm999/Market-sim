# tests/test_agent.py
"""Unit tests for simulator.agent (shared position keeping) and simulator.rng."""

import random

from lob.book import LimitOrderBook, Order
from simulator.agent import Agent, MarketTakingAgent
from simulator.rng import resolve


def make_book():
    return LimitOrderBook()


class _Taker(MarketTakingAgent):
    def __init__(self, size=5):
        super().__init__()
        self.size = size


# ---- position keeping ----


def test_agent_starts_flat():
    agent = Agent()

    assert agent.inventory == 0
    assert agent.cash == 0.0


def test_mark_to_market_is_cash_plus_inventory_at_mid():
    book = make_book()
    book.add_limit_order(Order(1, "buy", 99, 10))
    book.add_limit_order(Order(2, "sell", 101, 10))  # mid = 100

    agent = Agent()
    agent.inventory = 3
    agent.cash = -250.0

    assert agent.mark_to_market(book) == -250.0 + 3 * 100


def test_buying_adds_inventory_and_spends_cash():
    agent = Agent()
    agent._apply_trades([(100.0, 4)], "buy")

    assert agent.inventory == 4
    assert agent.cash == -400.0


def test_selling_removes_inventory_and_takes_in_cash():
    agent = Agent()
    agent._apply_trades([(100.0, 4)], "sell")

    assert agent.inventory == -4
    assert agent.cash == 400.0


def test_fills_across_levels_book_at_the_volume_weighted_average():
    agent = Agent()
    agent._apply_trades([(100.0, 1), (110.0, 3)], "buy")  # vwap = 107.5

    assert agent.inventory == 4
    assert agent.cash == -430.0


def test_an_empty_fill_list_changes_nothing():
    agent = Agent()
    agent._apply_trades([], "buy")

    assert agent.inventory == 0
    assert agent.cash == 0.0


# ---- market-taking ----


def test_market_order_books_only_what_actually_filled():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 2))  # only 2 available against a size-5 taker

    taker = _Taker(size=5)
    taker._execute_market_order(book, "buy")

    assert taker.inventory == 2
    assert taker.cash == -202.0


def test_market_order_against_an_empty_book_is_a_no_op():
    taker = _Taker(size=5)
    taker._execute_market_order(make_book(), "buy")

    assert taker.inventory == 0
    assert taker.cash == 0.0


def test_market_order_sweeps_levels_and_books_the_average():
    book = make_book()
    book.add_limit_order(Order(1, "sell", 101, 2))
    book.add_limit_order(Order(2, "sell", 103, 3))

    taker = _Taker(size=5)
    taker._execute_market_order(book, "buy")

    assert taker.inventory == 5
    assert taker.cash == -(2 * 101 + 3 * 103)


# ---- rng resolution ----


def test_resolve_returns_the_generator_it_was_given():
    rng = random.Random(0)

    assert resolve(rng) is rng


def test_resolve_falls_back_to_the_global_random_module():
    assert resolve(None) is random


def test_a_resolved_generator_is_reproducible():
    a = [resolve(random.Random(3)).random() for _ in range(3)]
    b = [resolve(random.Random(3)).random() for _ in range(3)]

    assert a == b
