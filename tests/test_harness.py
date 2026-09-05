# tests/test_harness.py
"""Unit tests for analysis.harness — the shared run-a-simulation routine."""

import random

from analysis.harness import default_imbalance_trader, informed_trader_for, run_simulation
from simulator.gbm_flow import generate_garch_gbm_path
from simulator.market_maker import MarketMaker


def prices(steps=60, seed=0):
    return generate_garch_gbm_path(steps, seed)


def make_market_maker():
    return MarketMaker(spread=2, size=5, max_inventory=50)


def test_run_is_deterministic_for_a_given_seed():
    path = prices()

    run_a = run_simulation(path, 3, make_market_maker(), default_imbalance_trader())
    run_b = run_simulation(path, 3, make_market_maker(), default_imbalance_trader())

    assert run_a.pnl == run_b.pnl
    assert run_a.metrics.mid_prices == run_b.metrics.mid_prices


def test_different_seeds_diverge():
    path = prices()

    run_a = run_simulation(path, 1, make_market_maker(), default_imbalance_trader())
    run_b = run_simulation(path, 2, make_market_maker(), default_imbalance_trader())

    assert run_a.metrics.mid_prices != run_b.metrics.mid_prices


def test_result_does_not_depend_on_global_random_state():
    """the reason each run builds its own random.Random: whatever else has been
    drawn from the module-global generator first must not change the answer."""
    path = prices()

    random.seed(0)
    baseline = run_simulation(path, 5, make_market_maker(), default_imbalance_trader()).pnl

    random.seed(12345)
    for _ in range(100):
        random.random()  # arbitrarily advance the global generator
    repeated = run_simulation(path, 5, make_market_maker(), default_imbalance_trader()).pnl

    assert baseline == repeated


def test_a_run_leaves_the_global_generator_untouched():
    path = prices()

    random.seed(21)
    before = random.random()

    random.seed(21)
    run_simulation(path, 5, make_market_maker(), default_imbalance_trader())
    after = random.random()

    assert before == after


def test_run_records_one_step_per_price():
    path = prices(steps=45)

    run = run_simulation(path, 0, make_market_maker(), default_imbalance_trader())

    assert len(run.metrics.mid_prices) == 45
    assert len(run.pnl_history.total_pnl) == 45


def test_pnl_property_matches_the_market_makers_mark_to_market():
    run = run_simulation(prices(), 0, make_market_maker(), default_imbalance_trader())

    assert run.pnl == run.market_maker.mark_to_market(run.book)


def test_agents_passed_in_are_the_ones_that_traded():
    imbalance_trader = default_imbalance_trader()
    informed = informed_trader_for([(10, 20, "buy")])

    run = run_simulation(prices(), 0, make_market_maker(), imbalance_trader, informed)

    assert run.imbalance_trader is imbalance_trader
    assert run.informed_trader is informed
    assert informed._step == len(run.metrics.mid_prices)


def test_informed_trader_only_trades_inside_its_window():
    informed = informed_trader_for([(10, 20, "buy")])

    run_simulation(prices(steps=40), 0, make_market_maker(), default_imbalance_trader(), informed)

    assert informed.inventory > 0  # bought during the window, never sold outside it
