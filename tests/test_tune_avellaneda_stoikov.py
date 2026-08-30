# tests/test_tune_avellaneda_stoikov.py
"""Unit tests for analysis.tune_avellaneda_stoikov."""

from analysis.tune_avellaneda_stoikov import SweepResult, run_one, summarize, sweep


def test_run_one_is_deterministic_for_a_given_seed():
    pnl_a = run_one(gamma=0.0001, k=1.5, seed=1, steps=20)
    pnl_b = run_one(gamma=0.0001, k=1.5, seed=1, steps=20)

    assert pnl_a == pnl_b


def test_sweep_returns_one_result_per_grid_cell():
    gammas = [0.0001, 0.0005]
    ks = [0.5, 1.5, 2.5]

    results = sweep(gammas=gammas, ks=ks, n_seeds=3)

    assert len(results) == len(gammas) * len(ks)
    assert all(isinstance(r, SweepResult) for r in results)

    seen = {(r.gamma, r.k) for r in results}
    expected = {(g, k) for g in gammas for k in ks}
    assert seen == expected


def test_summarize_does_not_crash_on_a_small_sweep(capsys):
    results = sweep(gammas=[0.0001, 0.0005], ks=[0.5, 1.5], n_seeds=3)

    summarize(results)

    assert "Best:" in capsys.readouterr().out
