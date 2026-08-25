# tests/test_compare_strategies.py
"""Unit tests for analysis.compare_strategies."""

from analysis.compare_strategies import RunResult, run_once, run_sweep, summarize


def test_run_once_is_deterministic_for_a_given_seed():
    result_a = run_once(seed=1, steps=20)
    result_b = run_once(seed=1, steps=20)

    assert result_a.market_maker_pnl == result_b.market_maker_pnl
    assert result_a.imbalance_trader_pnl == result_b.imbalance_trader_pnl


def test_different_seeds_can_produce_different_results():
    result_a = run_once(seed=1, steps=20)
    result_b = run_once(seed=2, steps=20)

    # Not a strict guarantee for any two arbitrary seeds, but true for this
    # seed pair under this setup - swap the seeds if this ever flakes.
    assert (result_a.market_maker_pnl, result_a.imbalance_trader_pnl) != (
        result_b.market_maker_pnl,
        result_b.imbalance_trader_pnl,
    )


def test_run_sweep_returns_one_result_per_seed():
    results = run_sweep(n_runs=5, steps=20)

    assert len(results) == 5
    assert [r.seed for r in results] == [0, 1, 2, 3, 4]
    assert all(isinstance(r, RunResult) for r in results)


def test_summarize_does_not_crash_on_a_small_sweep(capsys):
    results = run_sweep(n_runs=3, steps=20)

    summarize(results)

    assert "MarketMaker" in capsys.readouterr().out
