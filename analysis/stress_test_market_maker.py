# analysis/stress_test_market_maker.py
"""
Phase 3: feeds the market maker an InformedTrader with a known future
drift schedule and watches inventory_pnl take the hit live (adverse
selection), then checks whether wider vol-driven spreads and inventory
skew actually mitigate it.

Run (from the project root): python -m analysis.stress_test_market_maker
"""

import contextlib
import io
import random
import statistics
from dataclasses import dataclass
from typing import List, Sequence, Tuple

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from lob.book import LimitOrderBook, Side
from simulator.random_flow import simulate_random_flow
from simulator.market_maker import MarketMaker
from simulator.imbalance_trader import ImbalanceTrader
from simulator.informed_trader import InformedTrader
from metrics.pnl_history import PnLHistory

# Two 50-step drift windows (one of each direction), with plenty of plain
# random flow before/between/after so the book settles and each window's
# effect on inventory can fully mean-revert before the next one starts.
DEFAULT_SCHEDULE: List[Tuple[int, int, Side]] = [(150, 200, "buy"), (350, 400, "sell")]
STEPS = 600
REVERSION_WINDOW = 50  # steps after a window ends, used to measure mean-reversion speed
N_SEEDS = 30
VOL_COEFS: Tuple[float, ...] = (0.0, 1.0)
SKEW_COEFS: Tuple[float, ...] = (0.0, 1.0)


def run_one(
    vol_coef: float,
    skew_coef: float,
    seed: int,
    schedule: List[Tuple[int, int, Side]] = DEFAULT_SCHEDULE,
    steps: int = STEPS,
) -> PnLHistory:
    """One simulation under one (vol_coef, skew_coef) config and seed;
    returns the recorded PnLHistory for metric extraction."""
    random.seed(seed)

    book = LimitOrderBook()
    mm = MarketMaker(spread=2, size=5, max_inventory=50, vol_coef=vol_coef, skew_coef=skew_coef)
    it = ImbalanceTrader(threshold=0.4, size=5, max_inventory=50)
    informed = InformedTrader(schedule=schedule, size=4)
    history = PnLHistory()

    with contextlib.redirect_stdout(io.StringIO()):  # simulate_random_flow prints progress; silence it here
        simulate_random_flow(
            book,
            steps=steps,
            sleep=0,
            market_maker=mm,
            imbalance_trader=it,
            informed_trader=informed,
            pnl_history=history,
        )

    return history


def window_metrics(
    history: PnLHistory,
    schedule: List[Tuple[int, int, Side]] = DEFAULT_SCHEDULE,
    reversion_window: int = REVERSION_WINDOW,
) -> List[Tuple[float, float]]:
    """Per window: (drawdown, reversion).

    drawdown = worst inventory_pnl reached during the window, relative to
    just before it started — how hard adverse selection bit, in dollars.
    reversion = mean |inventory| over the `reversion_window` steps right
    after the window ends — how far the position is still from flat,
    in units. Lower is better for both.
    """
    results = []
    for start, end, _side in schedule:
        baseline = history.inventory_pnl[start - 1] if start > 0 else history.inventory_pnl[0]
        worst = min(history.inventory_pnl[start:end])
        drawdown = worst - baseline

        post = history.inventory[end : end + reversion_window]
        reversion = statistics.mean(abs(x) for x in post) if post else float("nan")
        results.append((drawdown, reversion))
    return results


@dataclass
class GridResult:
    vol_coef: float
    skew_coef: float
    mean_drawdown: float
    mean_reversion: float


def sweep(
    vol_coefs: Sequence[float] = VOL_COEFS,
    skew_coefs: Sequence[float] = SKEW_COEFS,
    n_seeds: int = N_SEEDS,
    schedule: List[Tuple[int, int, Side]] = DEFAULT_SCHEDULE,
    steps: int = STEPS,
) -> List[GridResult]:
    results = []
    for vol_coef in vol_coefs:
        for skew_coef in skew_coefs:
            drawdowns: List[float] = []
            reversions: List[float] = []
            for seed in range(n_seeds):
                history = run_one(vol_coef, skew_coef, seed, schedule, steps)
                for drawdown, reversion in window_metrics(history, schedule):
                    drawdowns.append(drawdown)
                    reversions.append(reversion)
            results.append(
                GridResult(
                    vol_coef=vol_coef,
                    skew_coef=skew_coef,
                    mean_drawdown=statistics.mean(drawdowns),
                    mean_reversion=statistics.mean(reversions),
                )
            )
    return results


def summarize(results: List[GridResult]) -> None:
    best_drawdown = max(results, key=lambda r: r.mean_drawdown)  # least negative = best protected
    best_reversion = min(results, key=lambda r: r.mean_reversion)  # smallest = fastest mean-reversion
    for r in results:
        markers = ""
        if r is best_drawdown:
            markers += "  <-- smallest drawdown"
        if r is best_reversion:
            markers += "  <-- fastest reversion"
        print(
            f"vol_coef={r.vol_coef:3.1f}  skew_coef={r.skew_coef:3.1f}  "
            f"mean_drawdown={r.mean_drawdown:9.2f}  mean_|inventory|_after={r.mean_reversion:6.2f}{markers}"
        )


def plot_grid(results: List[GridResult], save_path: str = "stress_test_grid.png") -> Figure:
    """Bar charts of mean drawdown and mean post-window |inventory|, one bar
    per (vol_coef, skew_coef) config, so the two questions Phase 3 asks are
    each answerable from a single glance."""
    labels = [f"vol={r.vol_coef:.0f}\nskew={r.skew_coef:.0f}" for r in results]
    drawdowns = [r.mean_drawdown for r in results]
    reversions = [r.mean_reversion for r in results]

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))

    axes[0].bar(labels, drawdowns, color="tab:red")
    axes[0].axhline(0, color="grey", linewidth=0.8)
    axes[0].set_ylabel("Mean inventory P&L drawdown during window")
    axes[0].set_title("Does spread widening protect you?")

    axes[1].bar(labels, reversions, color="tab:blue")
    axes[1].set_ylabel("Mean |inventory| in the 50 steps after a window")
    axes[1].set_title("Does inventory skew speed up mean-reversion?")

    fig.tight_layout()
    fig.savefig(save_path)
    return fig


def run_demo_scenario(
    seed: int = 42,
    schedule: List[Tuple[int, int, Side]] = DEFAULT_SCHEDULE,
    steps: int = STEPS,
) -> Tuple[MarketMaker, PnLHistory]:
    """Single seeded run at default vol_coef=1.0, skew_coef=1.0 - the
    'watch it happen live' scenario."""
    random.seed(seed)

    book = LimitOrderBook()
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    it = ImbalanceTrader(threshold=0.4, size=5, max_inventory=50)
    informed = InformedTrader(schedule=schedule, size=4)
    history = PnLHistory()

    with contextlib.redirect_stdout(io.StringIO()):
        simulate_random_flow(
            book,
            steps=steps,
            sleep=0,
            market_maker=mm,
            imbalance_trader=it,
            informed_trader=informed,
            pnl_history=history,
        )

    return mm, history


def plot_demo_scenario(
    history: PnLHistory,
    schedule: List[Tuple[int, int, Side]] = DEFAULT_SCHEDULE,
    save_path: str = "informed_trader_demo.png",
) -> Figure:
    """P&L split over time with the informed windows shaded - the direct
    'watch inventory_pnl go negative' visual."""
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(history.spread_pnl, label="Spread P&L", color="tab:blue")
    ax.plot(history.inventory_pnl, label="Inventory P&L", color="tab:red")
    ax.plot(history.total_pnl, label="Total P&L", linestyle="--", color="black")
    ax.axhline(0, color="grey", linewidth=0.8)

    for start, end, side in schedule:
        color = "tab:orange" if side == "buy" else "tab:purple"
        ax.axvspan(start, end, color=color, alpha=0.15, label=f"informed {side}")

    ax.set_xlabel("Step")
    ax.set_ylabel("P&L")
    ax.set_title("Market maker P&L around informed-trader drift windows (shaded)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(save_path)
    return fig


if __name__ == "__main__":
    mm, demo_history = run_demo_scenario()
    plot_demo_scenario(demo_history)
    print(
        f"informed_trader_demo.png saved. Final MarketMaker: "
        f"spread_pnl={mm.spread_pnl:.2f}, inventory_pnl={demo_history.inventory_pnl[-1]:.2f}"
    )

    print("\nRunning vol_coef x skew_coef grid...")
    results = sweep()
    summarize(results)
    plot_grid(results)
    print("\nSaved stress_test_grid.png")
