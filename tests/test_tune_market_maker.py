# tests/test_tune_market_maker.py
"""Unit tests for analysis.tune_market_maker."""

from analysis.tune_market_maker import SweepResult, run_one, summarize, sweep


def test_run_one_is_deterministic_for_a_given_seed():
    pnl_a = run_one(spread=2, max_inventory=50, seed=1, steps=20)
    pnl_b = run_one(spread=2, max_inventory=50, seed=1, steps=20)

    assert pnl_a == pnl_b


def test_sweep_returns_one_result_per_grid_cell():
    spreads = [1, 2]
    max_inventories = [10, 50, 100]

    results = sweep(spreads=spreads, max_inventories=max_inventories, n_seeds=3)

    assert len(results) == len(spreads) * len(max_inventories)
    assert all(isinstance(r, SweepResult) for r in results)

    seen = {(r.spread, r.max_inventory) for r in results}
    expected = {(s, m) for s in spreads for m in max_inventories}
    assert seen == expected


def test_summarize_does_not_crash_on_a_small_sweep(capsys):
    results = sweep(spreads=[1, 2], max_inventories=[10, 50], n_seeds=3)

    summarize(results)

    assert "Best:" in capsys.readouterr().out
