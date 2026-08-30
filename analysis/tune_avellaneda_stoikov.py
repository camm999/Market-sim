# analysis/tune_avellaneda_stoikov.py
"""
compare_strategies.py's AvellanedaStoikovMarketMaker sweep runs against
gamma/k picked to keep this sim's price scale stable, not tuned for
performance. This sweeps gamma (risk aversion) and k (order-arrival decay)
across a grid (ImbalanceTrader held fixed, same config as compare_strategies.py)
the same way tune_market_maker.py sweeps MarketMaker's own spread/max_inventory,
to check whether tuning closes more of the gap to ImbalanceTrader - gamma/k
aren't comparable to spread/max_inventory, so this is a separate script
rather than an extra axis on the same grid.

Run (from the project root): python -m analysis.tune_avellaneda_stoikov
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
from simulator.random_flow import simulate_random_flow
from simulator.avellaneda_stoikov import AvellanedaStoikovMarketMaker
from simulator.imbalance_trader import ImbalanceTrader

GAMMAS: List[float] = [0.00002, 0.00005, 0.0001, 0.0002, 0.0005, 0.001]
KS: List[float] = [0.5, 1.0, 1.5, 2.5, 4.0]
N_SEEDS = 50
STEPS = 500


@dataclass
class SweepResult:
    gamma: float
    k: float
    mean_pnl: float
    win_rate: float


def run_one(gamma: float, k: float, seed: int, steps: int = STEPS) -> float:
    """One simulation under one (gamma, k) config and one seed; returns
    AvellanedaStoikovMarketMaker's final mark-to-market P&L."""
    random.seed(seed)

    book = LimitOrderBook()
    mm = AvellanedaStoikovMarketMaker(size=5, max_inventory=50, gamma=gamma, k=k, total_steps=steps)
    it = ImbalanceTrader(threshold=0.4, size=5, max_inventory=50)  # held fixed throughout

    with contextlib.redirect_stdout(io.StringIO()):
        simulate_random_flow(book, steps=steps, sleep=0, market_maker=mm, imbalance_trader=it)

    return mm.mark_to_market(book)


def sweep(
    gammas: Sequence[float] = GAMMAS,
    ks: Sequence[float] = KS,
    n_seeds: int = N_SEEDS,
) -> List[SweepResult]:
    results = []
    for gamma in gammas:
        for k in ks:
            pnls = [run_one(gamma, k, seed) for seed in range(n_seeds)]
            wins = sum(1 for p in pnls if p > 0)
            results.append(SweepResult(gamma, k, statistics.mean(pnls), wins / len(pnls)))
    return results


def summarize(results: List[SweepResult]) -> None:
    best = max(results, key=lambda r: r.mean_pnl)
    for r in results:
        marker = "  <-- best" if r is best else ""
        print(
            f"gamma={r.gamma:.5f}  k={r.k:4.1f}  "
            f"mean_pnl={r.mean_pnl:9.2f}  win_rate={r.win_rate * 100:5.1f}%{marker}"
        )
    print(f"\nBest: gamma={best.gamma}, k={best.k}, mean_pnl={best.mean_pnl:.2f}")


def plot(
    results: List[SweepResult],
    gammas: Sequence[float] = GAMMAS,
    ks: Sequence[float] = KS,
    save_path: str = "images/avellaneda_stoikov_tuning.png",
) -> Figure:
    by_key = {(r.gamma, r.k): r.mean_pnl for r in results}
    grid = np.array([[by_key[(g, k)] for k in ks] for g in gammas])

    fig, ax = plt.subplots(figsize=(8, 6))
    vmax = np.abs(grid).max() or 1
    im = ax.imshow(grid, aspect="auto", origin="lower", cmap="RdYlGn", vmin=-vmax, vmax=vmax)

    ax.set_xticks(range(len(ks)))
    ax.set_xticklabels([str(k) for k in ks])
    ax.set_yticks(range(len(gammas)))
    ax.set_yticklabels([f"{g:.5f}" for g in gammas])
    ax.set_xlabel("k")
    ax.set_ylabel("gamma")
    ax.set_title("AvellanedaStoikovMarketMaker mean P&L by (gamma, k)")
    fig.colorbar(im, ax=ax, label="Mean P&L")
    fig.tight_layout()

    fig.savefig(save_path)
    return fig


if __name__ == "__main__":
    results = sweep()
    summarize(results)
    plot(results)
    print("\nSaved images/avellaneda_stoikov_tuning.png")
