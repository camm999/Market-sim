# tests/test_random_flow.py
"""Unit tests for simulator.random_flow — the Poisson-arrival order flow loop."""

import random

from lob.book import LimitOrderBook
from metrics.pnl_history import PnLHistory
from simulator.imbalance_trader import ImbalanceTrader
from simulator.informed_trader import InformedTrader
from simulator.market_maker import MarketMaker
from simulator.random_flow import random_limit_order, random_market_order, simulate_random_flow


def make_book():
    return LimitOrderBook()


def test_random_limit_order_lands_near_the_mid():
    book = make_book()
    rng = random.Random(0)

    for order_id in range(50):
        order = random_limit_order(book, order_id, rng)
        assert order.side in ("buy", "sell")
        assert 1 <= order.size <= 10
        assert abs(order.price - book.mid_price()) <= 3


def test_random_market_order_only_trades_against_resting_size():
    book = make_book()
    rng = random.Random(0)

    random_market_order(book, rng)  # empty book: nothing to hit

    assert book.trades == []


def test_runs_one_step_per_requested_step():
    book = make_book()
    metrics = simulate_random_flow(book, steps=25, sleep=0, rng=random.Random(1))

    assert len(metrics.mid_prices) == 25
    assert len(metrics.imbalances) == 25


def test_is_deterministic_for_a_given_rng_seed():
    metrics_a = simulate_random_flow(make_book(), steps=40, sleep=0, rng=random.Random(7))
    metrics_b = simulate_random_flow(make_book(), steps=40, sleep=0, rng=random.Random(7))

    assert metrics_a.mid_prices == metrics_b.mid_prices
    assert metrics_a.trade_prices == metrics_b.trade_prices


def test_different_rng_seeds_diverge():
    metrics_a = simulate_random_flow(make_book(), steps=60, sleep=0, rng=random.Random(1))
    metrics_b = simulate_random_flow(make_book(), steps=60, sleep=0, rng=random.Random(2))

    assert metrics_a.mid_prices != metrics_b.mid_prices


def test_an_explicit_rng_does_not_consume_global_random_state():
    """the whole point of passing an rng: a run can't be perturbed by, or perturb,
    anything else drawing from the module-global generator."""
    random.seed(99)
    before = random.random()

    random.seed(99)
    simulate_random_flow(make_book(), steps=30, sleep=0, rng=random.Random(4))
    after = random.random()

    assert before == after


def test_reseeding_the_global_generator_still_works_without_an_rng():
    """back-compat: callers that predate the rng argument keep their behaviour."""
    random.seed(5)
    metrics_a = simulate_random_flow(make_book(), steps=30, sleep=0)

    random.seed(5)
    metrics_b = simulate_random_flow(make_book(), steps=30, sleep=0)

    assert metrics_a.mid_prices == metrics_b.mid_prices


def test_only_limit_orders_arrive_when_lambda_market_is_zero():
    book = make_book()
    simulate_random_flow(
        book, steps=40, sleep=0, lambda_limit=1.0, lambda_market=0.0, rng=random.Random(3)
    )

    # every arrival rested or crossed as a limit order, so the book is never empty
    assert book.bids or book.asks


def test_agents_and_histories_are_driven_once_per_step():
    book = make_book()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    it = ImbalanceTrader(threshold=0.4, size=5, max_inventory=50)
    informed = InformedTrader(schedule=[(5, 10, "buy")], size=4)
    pnl_history = PnLHistory()

    simulate_random_flow(
        book,
        steps=30,
        sleep=0,
        market_maker=mm,
        imbalance_trader=it,
        informed_trader=informed,
        pnl_history=pnl_history,
        rng=random.Random(2),
    )

    assert len(pnl_history.total_pnl) == 30
    assert informed._step == 30  # act() called exactly once per step
    assert isinstance(mm.mark_to_market(book), float)
    assert isinstance(it.mark_to_market(book), float)
