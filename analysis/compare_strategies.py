# analysis/compare_strategies.py
"""
Runs the simulation across many random seeds and statistically compares
MarketMaker vs AvellanedaStoikovMarketMaker vs ImbalanceTrader performance
(mark-to-market P&L), instead of judging any agent off a single anecdotal
run.

Run (from the project root): python -m analysis.compare_strategies
"""

import contextlib
import io
import random
import statistics
from dataclasses import dataclass
from typing import List

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from lob.book import LimitOrderBook
from simulator.random_flow import simulate_random_flow
from simulator.market_maker import MarketMaker
from simulator.avellaneda_stoikov import AvellanedaStoikovMarketMaker
from simulator.imbalance_trader import ImbalanceTrader


@dataclass
class RunResult:
    seed: int
    market_maker_pnl: float
    avellaneda_pnl: float
    imbalance_trader_pnl: float


def run_once(seed: int, steps: int = 500) -> RunResult:
    """Run one full simulation under a given seed and return each agent's
    final mark-to-market P&L. Reseeding at the start makes every run fully
    reproducible regardless of how many other runs happened before it.

    MarketMaker and AvellanedaStoikovMarketMaker each get their own
    simulation rather than sharing one book: simulate_random_flow only ever
    quotes one market_maker per run, and since each MM's own resting quotes
    shape the book (see AvellanedaStoikovMarketMaker's docstring), a shared
    book wouldn't actually be a fair shared comparison anyway. Reseeding to
    the same seed before each keeps the *input* order flow identical
    between them; the *realized* flow still diverges once each MM starts
    quoting differently - the same caveat analysis/avellaneda_stoikov_demo.py
    already flags for its own head-to-head comparison. ImbalanceTrader's
    reported P&L comes from the MarketMaker run specifically, for the same
    reason - it isn't quoting into an identical book across both runs
    either, so a single reference figure is more honest than two divergent
    ones under one label.
    """
    random.seed(seed)
    book = LimitOrderBook()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    it = ImbalanceTrader(threshold=0.4, size=5, max_inventory=50)
    with contextlib.redirect_stdout(io.StringIO()):  # simulate_random_flow prints progress; silence it here
        simulate_random_flow(book, steps=steps, sleep=0, market_maker=mm, imbalance_trader=it)

    random.seed(seed)
    as_book = LimitOrderBook()
    as_mm = AvellanedaStoikovMarketMaker(size=5, max_inventory=50, total_steps=steps)
    as_it = ImbalanceTrader(threshold=0.4, size=5, max_inventory=50)
    with contextlib.redirect_stdout(io.StringIO()):
        simulate_random_flow(as_book, steps=steps, sleep=0, market_maker=as_mm, imbalance_trader=as_it)

    return RunResult(
        seed=seed,
        market_maker_pnl=mm.mark_to_market(book),
        avellaneda_pnl=as_mm.mark_to_market(as_book),
        imbalance_trader_pnl=it.mark_to_market(book),
    )


def run_sweep(n_runs: int = 200, steps: int = 500) -> List[RunResult]:
    return [run_once(seed, steps) for seed in range(n_runs)]


def summarize(results: List[RunResult]) -> None:
    mm_pnls = [r.market_maker_pnl for r in results]
    as_pnls = [r.avellaneda_pnl for r in results]
    it_pnls = [r.imbalance_trader_pnl for r in results]

    def report(name: str, pnls: List[float]) -> None:
        wins = sum(1 for p in pnls if p > 0)
        print(
            f"{name:18s} mean={statistics.mean(pnls):9.2f}  "
            f"stdev={statistics.stdev(pnls):8.2f}  "
            f"min={min(pnls):9.2f}  max={max(pnls):9.2f}  "
            f"profitable={wins}/{len(pnls)} ({wins / len(pnls) * 100:5.1f}%)"
        )

    def head_to_head(name_a: str, pnls_a: List[float], name_b: str, pnls_b: List[float]) -> None:
        wins = sum(1 for a, b in zip(pnls_a, pnls_b) if a > b)
        print(
            f"{name_a} beat {name_b} head-to-head in {wins}/{len(results)} runs "
            f"({wins / len(results) * 100:.1f}%)"
        )

    print(f"{len(results)} runs, {results[0].seed}-{results[-1].seed}\n")
    report("MarketMaker", mm_pnls)
    report("AvellanedaStoikov", as_pnls)
    report("ImbalanceTrader", it_pnls)

    print()
    head_to_head("MarketMaker", mm_pnls, "ImbalanceTrader", it_pnls)
    head_to_head("AvellanedaStoikov", as_pnls, "ImbalanceTrader", it_pnls)
    head_to_head("AvellanedaStoikov", as_pnls, "MarketMaker", mm_pnls)


def _scatter_vs(ax: Axes, x: List[float], y: List[float], xlabel: str, ylabel: str, title: str) -> None:
    ax.scatter(x, y, alpha=0.5, s=15)
    lo = min(x + y)
    hi = max(x + y)
    ax.plot([lo, hi], [lo, hi], color="gray", linewidth=0.8, linestyle="--")  # y = x reference
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)


def plot(results: List[RunResult], save_path: str = "images/strategy_comparison.png") -> Figure:
    mm_pnls = [r.market_maker_pnl for r in results]
    as_pnls = [r.avellaneda_pnl for r in results]
    it_pnls = [r.imbalance_trader_pnl for r in results]

    fig, axes = plt.subplots(1, 3, figsize=(17, 5))

    axes[0].hist(mm_pnls, bins=30, alpha=0.6, label="MarketMaker", color="tab:green")
    axes[0].hist(as_pnls, bins=30, alpha=0.6, label="AvellanedaStoikov", color="tab:blue")
    axes[0].hist(it_pnls, bins=30, alpha=0.6, label="ImbalanceTrader", color="tab:red")
    axes[0].axvline(0, color="black", linewidth=0.8, linestyle="--")
    axes[0].set_xlabel("Mark-to-market P&L")
    axes[0].set_ylabel("Number of runs")
    axes[0].set_title("P&L distribution across seeds")
    axes[0].legend()

    _scatter_vs(axes[1], mm_pnls, it_pnls, "MarketMaker P&L", "ImbalanceTrader P&L", "MarketMaker vs ImbalanceTrader")
    _scatter_vs(
        axes[2], as_pnls, mm_pnls, "AvellanedaStoikov P&L", "MarketMaker P&L", "AvellanedaStoikov vs MarketMaker"
    )

    fig.tight_layout()
    fig.savefig(save_path)
    return fig


if __name__ == "__main__":
    results = run_sweep(n_runs=200, steps=500)
    summarize(results)
    plot(results)
    print("\nSaved images/strategy_comparison.png")
