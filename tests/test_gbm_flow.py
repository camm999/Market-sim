# tests/test_gbm_flow.py
"""Unit tests for simulator.gbm_flow."""

import math
import random

from simulator.gbm_flow import (
    generate_gbm_path,
    generate_garch_gbm_path,
    generate_scheduled_drift_gbm_path,
    generate_scheduled_drift_garch_gbm_path,
)


def _excess_kurtosis(values):
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    m4 = sum((v - mean) ** 4 for v in values) / n
    return m4 / var**2 - 3


def _lag1_autocorr(values):
    n = len(values)
    mean = sum(values) / n
    num = sum((values[i] - mean) * (values[i + 1] - mean) for i in range(n - 1))
    den = sum((v - mean) ** 2 for v in values)
    return num / den


def test_generate_gbm_path_starts_at_base():
    prices = generate_gbm_path(steps=30, seed=1, base=100.0)

    assert prices[0] == 100.0


def test_generate_gbm_path_has_one_price_per_step():
    prices = generate_gbm_path(steps=30, seed=1)

    assert len(prices) == 30


def test_generate_gbm_path_is_deterministic_for_a_given_seed():
    prices_a = generate_gbm_path(steps=50, seed=7)
    prices_b = generate_gbm_path(steps=50, seed=7)

    assert prices_a == prices_b


def test_generate_gbm_path_diverges_across_seeds():
    prices_a = generate_gbm_path(steps=50, seed=1)
    prices_b = generate_gbm_path(steps=50, seed=2)

    assert prices_a != prices_b


def test_generate_gbm_path_stays_positive():
    prices = generate_gbm_path(steps=200, seed=3, sigma=0.05)

    assert all(p > 0 for p in prices)


def test_generate_gbm_path_does_not_consume_global_random_state():
    random.seed(123)
    before = random.random()

    random.seed(123)
    generate_gbm_path(steps=50, seed=1)
    after = random.random()

    assert before == after


def test_scheduled_drift_matches_plain_gbm_with_no_schedule():
    # An empty schedule means zero drift everywhere - identical to generate_gbm_path's own
    # driftless default, since both draw from the same per-step formula and RNG stream.
    plain = generate_gbm_path(steps=50, seed=4, mu=0.0, sigma=0.03)
    scheduled = generate_scheduled_drift_gbm_path(steps=50, seed=4, schedule=[], sigma=0.03)

    assert plain == scheduled


def test_scheduled_drift_is_deterministic_for_a_given_seed():
    schedule = [(5, 15, "buy")]

    prices_a = generate_scheduled_drift_gbm_path(steps=30, seed=7, schedule=schedule)
    prices_b = generate_scheduled_drift_gbm_path(steps=30, seed=7, schedule=schedule)

    assert prices_a == prices_b


def test_scheduled_drift_stays_positive():
    schedule = [(10, 60, "sell")]

    prices = generate_scheduled_drift_gbm_path(steps=100, seed=3, schedule=schedule, drift=0.01, sigma=0.05)

    assert all(p > 0 for p in prices)


def test_scheduled_drift_pushes_price_up_during_a_buy_window():
    # Zero noise isolates the drift term entirely, so this checks direction deterministically
    # rather than relying on one seed happening to trend the right way despite the noise.
    schedule = [(0, 20, "buy")]

    prices = generate_scheduled_drift_gbm_path(steps=20, seed=1, schedule=schedule, drift=0.05, sigma=0.0)

    assert prices[-1] > prices[0]


def test_scheduled_drift_pushes_price_down_during_a_sell_window():
    schedule = [(0, 20, "sell")]

    prices = generate_scheduled_drift_gbm_path(steps=20, seed=1, schedule=schedule, drift=0.05, sigma=0.0)

    assert prices[-1] < prices[0]


def test_scheduled_drift_is_flat_outside_any_window():
    # No drift before or after the one window, and zero noise, so the pre- and post-window
    # segments should be perfectly flat while the windowed segment moves. prices[t+1] is what
    # picks up window t's drift, so the window (40, 60) first shows up at index 41 and last
    # affects index 60.
    schedule = [(40, 60, "buy")]

    prices = generate_scheduled_drift_gbm_path(steps=100, seed=2, schedule=schedule, drift=0.05, sigma=0.0)

    assert prices[40] == prices[0]  # flat up to (not including) the window
    assert prices[99] == prices[60]  # flat after the window
    assert prices[60] > prices[40]  # moved during the window


def test_generate_garch_gbm_path_starts_at_base():
    prices = generate_garch_gbm_path(steps=30, seed=1, base=100.0)

    assert prices[0] == 100.0


def test_generate_garch_gbm_path_has_one_price_per_step():
    prices = generate_garch_gbm_path(steps=30, seed=1)

    assert len(prices) == 30


def test_generate_garch_gbm_path_is_deterministic_for_a_given_seed():
    prices_a = generate_garch_gbm_path(steps=50, seed=7)
    prices_b = generate_garch_gbm_path(steps=50, seed=7)

    assert prices_a == prices_b


def test_generate_garch_gbm_path_diverges_across_seeds():
    prices_a = generate_garch_gbm_path(steps=50, seed=1)
    prices_b = generate_garch_gbm_path(steps=50, seed=2)

    assert prices_a != prices_b


def test_generate_garch_gbm_path_stays_positive():
    prices = generate_garch_gbm_path(steps=200, seed=3, alpha=0.15, beta=0.8)

    assert all(p > 0 for p in prices)


def test_generate_garch_gbm_path_does_not_consume_global_random_state():
    random.seed(123)
    before = random.random()

    random.seed(123)
    generate_garch_gbm_path(steps=50, seed=1)
    after = random.random()

    assert before == after


def test_generate_garch_gbm_path_has_fatter_tails_than_plain_gbm():
    # Same seed/steps/unconditional-vol for both, so this isolates the distributional
    # shape (Student-t + GARCH clustering vs. constant-sigma Gaussian), not scale.
    garch_prices = generate_garch_gbm_path(steps=5000, seed=1)
    plain_prices = generate_gbm_path(steps=5000, seed=1, sigma=0.02)

    garch_returns = [math.log(garch_prices[i + 1] / garch_prices[i]) for i in range(len(garch_prices) - 1)]
    plain_returns = [math.log(plain_prices[i + 1] / plain_prices[i]) for i in range(len(plain_prices) - 1)]

    assert _excess_kurtosis(garch_returns) > _excess_kurtosis(plain_returns) + 1.0


def test_generate_garch_gbm_path_has_volatility_clustering():
    # Plain GBM has constant sigma, so squared returns are uncorrelated over a long run;
    # GARCH's variance recursion should show a clear positive lag-1 autocorrelation instead.
    garch_prices = generate_garch_gbm_path(steps=5000, seed=1)
    plain_prices = generate_gbm_path(steps=5000, seed=1, sigma=0.02)

    garch_sq_returns = [
        math.log(garch_prices[i + 1] / garch_prices[i]) ** 2 for i in range(len(garch_prices) - 1)
    ]
    plain_sq_returns = [
        math.log(plain_prices[i + 1] / plain_prices[i]) ** 2 for i in range(len(plain_prices) - 1)
    ]

    assert _lag1_autocorr(garch_sq_returns) > 0.05
    assert _lag1_autocorr(garch_sq_returns) > _lag1_autocorr(plain_sq_returns)


def test_garch_scheduled_drift_matches_plain_garch_with_no_schedule():
    plain = generate_garch_gbm_path(steps=50, seed=4)
    scheduled = generate_scheduled_drift_garch_gbm_path(steps=50, seed=4, schedule=[])

    assert plain == scheduled


def test_garch_scheduled_drift_is_deterministic_for_a_given_seed():
    schedule = [(5, 15, "buy")]

    prices_a = generate_scheduled_drift_garch_gbm_path(steps=30, seed=7, schedule=schedule)
    prices_b = generate_scheduled_drift_garch_gbm_path(steps=30, seed=7, schedule=schedule)

    assert prices_a == prices_b


def test_garch_scheduled_drift_stays_positive():
    schedule = [(10, 60, "sell")]

    prices = generate_scheduled_drift_garch_gbm_path(steps=100, seed=3, schedule=schedule, drift=0.01)

    assert all(p > 0 for p in prices)


def test_garch_scheduled_drift_pushes_price_up_during_a_buy_window():
    schedule = [(0, 20, "buy")]

    prices = generate_scheduled_drift_garch_gbm_path(
        steps=20, seed=1, schedule=schedule, drift=0.05, alpha=0.0, beta=0.0, omega=0.0
    )

    assert prices[-1] > prices[0]


def test_garch_scheduled_drift_pushes_price_down_during_a_sell_window():
    schedule = [(0, 20, "sell")]

    prices = generate_scheduled_drift_garch_gbm_path(
        steps=20, seed=1, schedule=schedule, drift=0.05, alpha=0.0, beta=0.0, omega=0.0
    )

    assert prices[-1] < prices[0]
