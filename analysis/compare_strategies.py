# analysis/compare_strategies.py
"""
Runs the simulation across many random seeds and statistically compares
MarketMaker vs ImbalanceTrader performance (mark-to-market P&L), instead
of judging either agent off a single anecdotal run.

Run (from the project root): python -m analysis.compare_strategies
"""

import contextlib
import io
import random
import statistics
from dataclasses import dataclass
from typing import List

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from lob.book import LimitOrderBook
from simulator.random_flow import simulate_random_flow
from simulator.market_maker import MarketMaker
from simulator.imbalance_trader import ImbalanceTrader


@dataclass
class RunResult:
    seed: int
    market_maker_pnl: float
    imbalance_trader_pnl: float


def run_once(seed: int, steps: int = 500) -> RunResult:
    """Run one full simulation under a given seed and return each agent's
    final mark-to-market P&L. Reseeding at the start makes every run fully
    reproducible regardless of how many other runs happened before it."""
    random.seed(seed)

    book = LimitOrderBook()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    it = ImbalanceTrader(threshold=0.4, size=5, max_inventory=50)

    with contextlib.redirect_stdout(io.StringIO()):  # simulate_random_flow prints progress; silence it here
        simulate_random_flow(book, steps=steps, sleep=0, market_maker=mm, imbalance_trader=it)

    return RunResult(
        seed=seed,
        market_maker_pnl=mm.mark_to_market(book),
        imbalance_trader_pnl=it.mark_to_market(book),
    )


def run_sweep(n_runs: int = 200, steps: int = 500) -> List[RunResult]:
    return [run_once(seed, steps) for seed in range(n_runs)]


def summarize(results: List[RunResult]) -> None:
    mm_pnls = [r.market_maker_pnl for r in results]
    it_pnls = [r.imbalance_trader_pnl for r in results]

    def report(name: str, pnls: List[float]) -> None:
        wins = sum(1 for p in pnls if p > 0)
        print(
            f"{name:16s} mean={statistics.mean(pnls):9.2f}  "
            f"stdev={statistics.stdev(pnls):8.2f}  "
            f"min={min(pnls):9.2f}  max={max(pnls):9.2f}  "
            f"profitable={wins}/{len(pnls)} ({wins / len(pnls) * 100:5.1f}%)"
        )

    print(f"{len(results)} runs, {results[0].seed}-{results[-1].seed}\n")
    report("MarketMaker", mm_pnls)
    report("ImbalanceTrader", it_pnls)

    mm_wins = sum(1 for r in results if r.market_maker_pnl > r.imbalance_trader_pnl)
    print(
        f"\nMarketMaker beat ImbalanceTrader head-to-head in {mm_wins}/{len(results)} runs "
        f"({mm_wins / len(results) * 100:.1f}%)"
    )


def plot(results: List[RunResult], save_path: str = "images/strategy_comparison.png") -> Figure:
    mm_pnls = [r.market_maker_pnl for r in results]
    it_pnls = [r.imbalance_trader_pnl for r in results]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    axes[0].hist(mm_pnls, bins=30, alpha=0.6, label="MarketMaker", color="tab:green")
    axes[0].hist(it_pnls, bins=30, alpha=0.6, label="ImbalanceTrader", color="tab:red")
    axes[0].axvline(0, color="black", linewidth=0.8, linestyle="--")
    axes[0].set_xlabel("Mark-to-market P&L")
    axes[0].set_ylabel("Number of runs")
    axes[0].set_title("P&L distribution across seeds")
    axes[0].legend()

    axes[1].scatter(mm_pnls, it_pnls, alpha=0.5, s=15)
    lo = min(mm_pnls + it_pnls)
    hi = max(mm_pnls + it_pnls)
    axes[1].plot([lo, hi], [lo, hi], color="gray", linewidth=0.8, linestyle="--")  # y = x reference
    axes[1].set_xlabel("MarketMaker P&L")
    axes[1].set_ylabel("ImbalanceTrader P&L")
    axes[1].set_title("Per-seed P&L: MarketMaker vs ImbalanceTrader")

    fig.tight_layout()
    fig.savefig(save_path)
    return fig


if __name__ == "__main__":
    results = run_sweep(n_runs=200, steps=500)
    summarize(results)
    plot(results)
    print("\nSaved images/strategy_comparison.png")
