# analysis/avellaneda_stoikov_demo.py
"""
replaces MarketMaker's linear vol/skew heuristic with the actual
Avellaneda-Stoikov reservation-price model (see simulator/avellaneda_stoikov.py)
and compares them head-to-head under the same informed-trader adverse-selection
stress scenario from (analysis/stress_test_market_maker.py), also see
something the linear heuristic can't do, flatten quotes toward a trading horizon.

both MMs are ran in separate simulations rather than side by side in one book, simulate_historical_flow only
ever quotes one market_maker per run, and since each MM's own quotes shape the book a shared-book
comparison wouldn't actually be shared.

Both anchored to a GARCH(1,1)/ Student-t GBM price path


Run (from the project root): python -m analysis.avellaneda_stoikov_demo
"""

from typing import Any, List, Tuple

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from analysis.harness import default_imbalance_trader, informed_trader_for, run_simulation
from lob.book import LimitOrderBook, Side
from simulator.gbm_flow import generate_scheduled_drift_garch_gbm_path
from simulator.market_maker import MarketMaker
from simulator.avellaneda_stoikov import AvellanedaStoikovMarketMaker
from metrics.pnl_history import PnLHistory
from analysis.stress_test_market_maker import DEFAULT_SCHEDULE, GARCH_OMEGA, STEPS


class _RecordingASMarketMaker(AvellanedaStoikovMarketMaker):
    """same quoting model as AvellanedaStoikovMarketMaker, records
    quoted reservation price and half-spread each step, purely for the
    horizon decay plot below"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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
    prices = generate_scheduled_drift_garch_gbm_path(steps, seed, schedule, omega=GARCH_OMEGA)
    mm = MarketMaker(spread=2, size=5, max_inventory=50)

    run = run_simulation(
        prices, seed, mm, default_imbalance_trader(), informed_trader_for(schedule)
    )
    return mm, run.pnl_history


def run_avellaneda_stoikov(
    seed: int = 42,
    schedule: List[Tuple[int, int, Side]] = DEFAULT_SCHEDULE,
    steps: int = STEPS,
) -> Tuple[_RecordingASMarketMaker, PnLHistory]:
    prices = generate_scheduled_drift_garch_gbm_path(steps, seed, schedule, omega=GARCH_OMEGA)
    mm = _RecordingASMarketMaker(size=5, max_inventory=50, total_steps=steps)

    run = run_simulation(
        prices, seed, mm, default_imbalance_trader(), informed_trader_for(schedule)
    )
    return mm, run.pnl_history


def plot_comparison(
    heuristic_history: PnLHistory,
    as_history: PnLHistory,
    schedule: List[Tuple[int, int, Side]] = DEFAULT_SCHEDULE,
    save_path: str = "images/avellaneda_stoikov_comparison.png",
) -> Figure:
    """spread/inventory/total p&l for both MMs, same informed trader windows
    shaded on both """
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
    """Reservation price and quoted half-spread over the run """
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
