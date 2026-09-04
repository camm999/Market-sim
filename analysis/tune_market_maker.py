# analysis/tune_market_maker.py
"""
compare_strategies.py found MarketMaker losing to ImbalanceTrader across
200 seeds. This sweeps MarketMaker's spread and max_inventory across a
grid to check if there's a tuning problem.

Each run is Anchored to a GARCH(1,1)/ Student-t GBM price path  

Run (from the project root): python -m analysis.tune_market_maker
"""

import contextlib
import io
import random
import statistics
from dataclasses import dataclass
from typing import List, Sequence

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from lob.book import LimitOrderBook
from simulator.gbm_flow import generate_garch_gbm_path
from simulator.historical_flow import simulate_historical_flow
from simulator.market_maker import MarketMaker
from simulator.imbalance_trader import ImbalanceTrader

SPREADS: List[float] = [1, 2, 3, 4, 6, 8]
MAX_INVENTORIES: List[int] = [10, 20, 50, 100, 200]
N_SEEDS = 50
STEPS = 500


@dataclass
class SweepResult:
    spread: float
    max_inventory: int
    mean_pnl: float
    win_rate: float


def run_one(spread: float, max_inventory: int, seed: int, steps: int = STEPS) -> float:
    """one simulation under one (spread, max_inventory) config and one seed;
    returns MarketMaker's final mark-to-market P&L """
    prices = generate_garch_gbm_path(steps, seed)
    random.seed(seed)

    book = LimitOrderBook()
    mm = MarketMaker(spread=spread, size=5, max_inventory=max_inventory)
    it = ImbalanceTrader(threshold=0.4, size=5, max_inventory=50)  # held fixed throughout

    with contextlib.redirect_stdout(io.StringIO()):
        simulate_historical_flow(book, prices, market_maker=mm, imbalance_trader=it)

    return mm.mark_to_market(book)


def sweep(
    spreads: Sequence[float] = SPREADS,
    max_inventories: Sequence[int] = MAX_INVENTORIES,
    n_seeds: int = N_SEEDS,
) -> List[SweepResult]:
    results = []
    for spread in spreads:
        for max_inv in max_inventories:
            pnls = [run_one(spread, max_inv, seed) for seed in range(n_seeds)]
            wins = sum(1 for p in pnls if p > 0)
            results.append(SweepResult(spread, max_inv, statistics.mean(pnls), wins / len(pnls)))
    return results


def summarize(results: List[SweepResult]) -> None:
    best = max(results, key=lambda r: r.mean_pnl)
    for r in results:
        marker = "  <-- best" if r is best else ""
        print(
            f"spread={r.spread:4.1f}  max_inventory={r.max_inventory:4d}  "
            f"mean_pnl={r.mean_pnl:9.2f}  win_rate={r.win_rate * 100:5.1f}%{marker}"
        )
    print(f"\nBest: spread={best.spread}, max_inventory={best.max_inventory}, mean_pnl={best.mean_pnl:.2f}")


def plot(
    results: List[SweepResult],
    spreads: Sequence[float] = SPREADS,
    max_inventories: Sequence[int] = MAX_INVENTORIES,
    save_path: str = "images/market_maker_tuning.png",
) -> Figure:
    by_key = {(r.spread, r.max_inventory): r.mean_pnl for r in results}
    grid = np.array([[by_key[(s, m)] for m in max_inventories] for s in spreads])

    fig, ax = plt.subplots(figsize=(8, 6))
    vmax = np.abs(grid).max() or 1
    im = ax.imshow(grid, aspect="auto", origin="lower", cmap="RdYlGn", vmin=-vmax, vmax=vmax)

    ax.set_xticks(range(len(max_inventories)))
    ax.set_xticklabels([str(m) for m in max_inventories])
    ax.set_yticks(range(len(spreads)))
    ax.set_yticklabels([str(s) for s in spreads])
    ax.set_xlabel("max_inventory")
    ax.set_ylabel("spread")
    ax.set_title("MarketMaker mean P&L by (spread, max_inventory)")
    fig.colorbar(im, ax=ax, label="Mean P&L")
    fig.tight_layout()

    fig.savefig(save_path)
    return fig


if __name__ == "__main__":
    results = sweep()
    summarize(results)
    plot(results)
    print("\nSaved images/market_maker_tuning.png")
