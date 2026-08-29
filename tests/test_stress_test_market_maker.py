# tests/test_stress_test_market_maker.py
"""Unit tests for analysis.stress_test_market_maker."""

from analysis.stress_test_market_maker import (
    GridResult,
    run_one,
    summarize,
    sweep,
    window_metrics,
)

SMALL_SCHEDULE = [(5, 10, "buy"), (15, 20, "sell")]


def test_run_one_is_deterministic_for_a_given_seed():
    history_a = run_one(vol_coef=1.0, skew_coef=1.0, seed=1, schedule=SMALL_SCHEDULE, steps=30)
    history_b = run_one(vol_coef=1.0, skew_coef=1.0, seed=1, schedule=SMALL_SCHEDULE, steps=30)

    assert history_a.inventory_pnl == history_b.inventory_pnl
    assert history_a.inventory == history_b.inventory


def test_window_metrics_returns_one_pair_per_window():
    history = run_one(vol_coef=1.0, skew_coef=1.0, seed=1, schedule=SMALL_SCHEDULE, steps=30)

    results = window_metrics(history, schedule=SMALL_SCHEDULE, reversion_window=5)

    assert len(results) == len(SMALL_SCHEDULE)
    for drawdown, reversion in results:
        assert isinstance(drawdown, float)
        assert isinstance(reversion, float)


def test_sweep_returns_one_result_per_grid_cell():
    vol_coefs = (0.0, 1.0)
    skew_coefs = (0.0, 1.0)

    results = sweep(
        vol_coefs=vol_coefs,
        skew_coefs=skew_coefs,
        n_seeds=2,
        schedule=SMALL_SCHEDULE,
        steps=30,
    )

    assert len(results) == len(vol_coefs) * len(skew_coefs)
    assert all(isinstance(r, GridResult) for r in results)

    seen = {(r.vol_coef, r.skew_coef) for r in results}
    expected = {(v, s) for v in vol_coefs for s in skew_coefs}
    assert seen == expected


def test_summarize_does_not_crash_on_a_small_sweep(capsys):
    results = sweep(
        vol_coefs=(0.0, 1.0),
        skew_coefs=(0.0, 1.0),
        n_seeds=2,
        schedule=SMALL_SCHEDULE,
        steps=30,
    )

    summarize(results)

    assert "vol_coef" in capsys.readouterr().out
