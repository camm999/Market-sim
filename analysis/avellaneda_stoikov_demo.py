# analysis/avellaneda_stoikov_demo.py
"""
Phase 4: replaces MarketMaker's linear vol/skew heuristic with the actual
Avellaneda-Stoikov reservation-price model (see simulator/avellaneda_stoikov.py)
and compares them head-to-head under the same informed-trader adverse-selection
stress scenario from Phase 3 (analysis/stress_test_market_maker.py), plus a
look at the one thing the linear heuristic can't do at all: flatten quotes
toward a trading horizon.

Both MMs are run in separate simulations (same seed, same informed-trader
schedule) rather than side by side in one book — simulate_random_flow only
ever quotes one market_maker per run, and since each MM's own quotes shape
the book (see the AvellanedaStoikovMarketMaker docstring), a shared-book
comparison wouldn't actually be shared. Same seed keeps the *input* flow
identical; the *realized* flow still diverges once each MM starts quoting
differently — the same caveat analysis/stress_test_market_maker.py already
flags for its vol_coef x skew_coef grid.

Run (from the project root): python -m analysis.avellaneda_stoikov_demo
"""

import contextlib
import io
import random
from typing import List, Tuple

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from lob.book import LimitOrderBook, Side
from simulator.random_flow import simulate_random_flow
from simulator.market_maker import MarketMaker
from simulator.avellaneda_stoikov import AvellanedaStoikovMarketMaker
from simulator.imbalance_trader import ImbalanceTrader
from simulator.informed_trader import InformedTrader
from metrics.pnl_history import PnLHistory
from analysis.stress_test_market_maker import DEFAULT_SCHEDULE, STEPS


class _RecordingASMarketMaker(AvellanedaStoikovMarketMaker):
    """Same quoting model as AvellanedaStoikovMarketMaker; also records the
    quoted reservation price and half-spread each step, purely for the
    horizon-decay plot below - not something the model itself needs."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.reservation_history: List[float] = []
        self.half_spread_history: List[float] = []

    def _reservation_and_half_spread(self, book: LimitOrderBook, mid: float) -> Tuple[float, float]:
        reservation, half = super()._reservation_and_half_spread(book, mid)
        self.reservation_history.append(reservation)
        self.half_spread_history.append(half)
        return reservation, half


def run_heuristic(
    seed: int = 42,
    schedule: List[Tuple[int, int, Side]] = DEFAULT_SCHEDULE,
    steps: int = STEPS,
) -> Tuple[MarketMaker, PnLHistory]:
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


def run_avellaneda_stoikov(
    seed: int = 42,
    schedule: List[Tuple[int, int, Side]] = DEFAULT_SCHEDULE,
    steps: int = STEPS,
) -> Tuple[_RecordingASMarketMaker, PnLHistory]:
    random.seed(seed)
    book = LimitOrderBook()
    mm = _RecordingASMarketMaker(size=5, max_inventory=50, total_steps=steps)
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


def plot_comparison(
    heuristic_history: PnLHistory,
    as_history: PnLHistory,
    schedule: List[Tuple[int, int, Side]] = DEFAULT_SCHEDULE,
    save_path: str = "images/avellaneda_stoikov_comparison.png",
) -> Figure:
    """Spread/inventory/total P&L for both MMs, same informed-trader windows
    shaded on both - the head-to-head version of stress_test_market_maker.py's
    plot_demo_scenario."""
    fig, axes = plt.subplots(2, 1, figsize=(10, 9), sharex=True)

    for ax, history, title in (
        (axes[0], heuristic_history, "MarketMaker (linear vol/skew heuristic)"),
        (axes[1], as_history, "AvellanedaStoikovMarketMaker"),
    ):
        ax.plot(history.spread_pnl, label="Spread P&L", color="tab:blue")
        ax.plot(history.inventory_pnl, label="Inventory P&L", color="tab:red")
        ax.plot(history.total_pnl, label="Total P&L", linestyle="--", color="black")
        ax.axhline(0, color="grey", linewidth=0.8)
        for start, end, side in schedule:
            color = "tab:orange" if side == "buy" else "tab:purple"
            ax.axvspan(start, end, color=color, alpha=0.15)
        ax.set_ylabel("P&L")
        ax.set_title(title)
        ax.legend()

    axes[1].set_xlabel("Step")
    fig.tight_layout()
    fig.savefig(save_path)
    return fig


def plot_horizon_decay(
    mm: _RecordingASMarketMaker,
    schedule: List[Tuple[int, int, Side]] = DEFAULT_SCHEDULE,
    save_path: str = "images/avellaneda_stoikov_horizon_decay.png",
) -> Figure:
    """Reservation price and quoted half-spread over the run - the plot that
    shows the model doing something the linear heuristic structurally can't:
    both the inventory skew and the variance-driven part of the spread are
    scaled by time_remaining, so they shrink toward the end of the horizon
    regardless of what inventory or volatility are doing at that moment."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

    ax1.plot(mm.reservation_history, color="tab:green")
    for start, end, side in schedule:
        color = "tab:orange" if side == "buy" else "tab:purple"
        ax1.axvspan(start, end, color=color, alpha=0.15)
    ax1.set_ylabel("Reservation price")
    ax1.set_title("Avellaneda-Stoikov: reservation price and quoted half-spread over the run")

    ax2.plot(mm.half_spread_history, color="tab:brown")
    ax2.axvline(mm.total_steps, color="grey", linestyle=":", linewidth=1, label="horizon (T)")
    ax2.set_ylabel("Half-spread")
    ax2.set_xlabel("Step")
    ax2.legend()

    fig.tight_layout()
    fig.savefig(save_path)
    return fig


if __name__ == "__main__":
    heuristic_mm, heuristic_history = run_heuristic()
    as_mm, as_history = run_avellaneda_stoikov()

    print(
        f"MarketMaker:                 spread_pnl={heuristic_mm.spread_pnl:.2f}, "
        f"inventory_pnl={heuristic_history.inventory_pnl[-1]:.2f}, "
        f"total={heuristic_history.total_pnl[-1]:.2f}"
    )
    print(
        f"AvellanedaStoikovMarketMaker: spread_pnl={as_mm.spread_pnl:.2f}, "
        f"inventory_pnl={as_history.inventory_pnl[-1]:.2f}, "
        f"total={as_history.total_pnl[-1]:.2f}"
    )

    plot_comparison(heuristic_history, as_history)
    print("\nSaved images/avellaneda_stoikov_comparison.png")

    plot_horizon_decay(as_mm)
    print("Saved images/avellaneda_stoikov_horizon_decay.png")
