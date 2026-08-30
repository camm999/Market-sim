# tests/test_historical_flow.py
"""Unit tests for simulator.historical_flow."""

import csv
import random

import pytest

from lob.book import LimitOrderBook
from simulator.historical_flow import load_price_series, rescale_to_sim_scale, simulate_historical_flow
from simulator.imbalance_trader import ImbalanceTrader
from simulator.market_maker import MarketMaker


@pytest.fixture
def price_csv(tmp_path):
    path = tmp_path / "prices.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "close"])
        writer.writerow(["2024-01-01T00:00:00Z", "100.0"])
        writer.writerow(["2024-01-01T00:01:00Z", "101.0"])
        writer.writerow(["2024-01-01T00:02:00Z", "99.0"])
    return str(path)


def test_load_price_series_reads_close_column(price_csv):
    prices = load_price_series(price_csv)

    assert prices == [100.0, 101.0, 99.0]


def test_rescale_to_sim_scale_starts_at_base():
    rescaled = rescale_to_sim_scale([100.0, 101.0, 99.0], base=100.0)

    assert rescaled[0] == 100.0


def test_rescale_to_sim_scale_preserves_percentage_returns():
    # +1% then -1% (of the new level, not the original) should replay
    # exactly onto a rescaled series starting at a different base.
    rescaled = rescale_to_sim_scale([100.0, 101.0, 99.99], base=50.0)

    assert rescaled[0] == 50.0
    assert rescaled[1] == pytest.approx(50.5)  # 50 * 1.01
    assert rescaled[2] == pytest.approx(50.5 * (99.99 / 101.0))


def test_rescale_to_sim_scale_handles_empty_input():
    assert rescale_to_sim_scale([]) == []


def test_simulate_historical_flow_runs_one_step_per_price():
    random.seed(1)
    book = LimitOrderBook()
    prices = rescale_to_sim_scale([100.0] * 30)

    metrics = simulate_historical_flow(book, prices)

    assert len(metrics.mid_prices) == len(prices)


def test_simulate_historical_flow_is_deterministic_for_a_given_seed():
    prices = rescale_to_sim_scale([100.0, 102.0, 98.0, 103.0] * 10)

    random.seed(7)
    book_a = LimitOrderBook()
    metrics_a = simulate_historical_flow(book_a, prices)

    random.seed(7)
    book_b = LimitOrderBook()
    metrics_b = simulate_historical_flow(book_b, prices)

    assert metrics_a.mid_prices == metrics_b.mid_prices


def test_simulate_historical_flow_with_market_maker_and_imbalance_trader():
    random.seed(3)
    book = LimitOrderBook()
    prices = rescale_to_sim_scale([100.0 + i * 0.1 for i in range(50)])
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    it = ImbalanceTrader(threshold=0.4, size=5, max_inventory=50)

    simulate_historical_flow(book, prices, market_maker=mm, imbalance_trader=it)

    # No crash, and both agents produced a well-defined mark-to-market.
    assert isinstance(mm.mark_to_market(book), float)
    assert isinstance(it.mark_to_market(book), float)
