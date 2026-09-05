# analysis/historical_backtest.py
"""
Runs MarketMaker and AvellanedaStoikovMarketMaker against a real historical
price series (BTCUSDT 1-minute closes from Binance, see data/btcusdt_1m.csv)
so the agents' fair-value process is exogenous and genuinely can't be influenced by their
own quotes, see ANALYSIS.md

Run (from the project root): python -m analysis.historical_backtest
"""

from typing import List, Tuple

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from analysis.harness import default_imbalance_trader, run_simulation
from metrics.metrics import Metrics
from metrics.pnl_history import PnLHistory
from simulator.avellaneda_stoikov import AvellanedaStoikovMarketMaker
from simulator.historical_flow import load_price_series, rescale_to_sim_scale
from simulator.market_maker import MarketMaker

DATA_PATH = "data/btcusdt_1m.csv"
STEPS = 500
SEED = 42


def run_market_maker(prices: List[float], seed: int = SEED) -> Tuple[MarketMaker, Metrics, PnLHistory]:
    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    run = run_simulation(prices, seed, mm, default_imbalance_trader())
    return mm, run.metrics, run.pnl_history


def run_avellaneda_stoikov(
    prices: List[float], seed: int = SEED
) -> Tuple[AvellanedaStoikovMarketMaker, Metrics, PnLHistory]:
    mm = AvellanedaStoikovMarketMaker(size=5, max_inventory=50, total_steps=len(prices))
    run = run_simulation(prices, seed, mm, default_imbalance_trader())
    return mm, run.metrics, run.pnl_history


def plot_price_tracking(
    prices: List[float],
    mm_metrics: Metrics,
    as_metrics: Metrics,
    save_path: str = "images/historical_backtest_price.png",
) -> Figure:
    """real (rescaled) price path vs. each market maker's own simulated
    book mid. gives direct read on which market maker's own resting quotes
    perturb the book furthest from the true exogenous price """
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(prices, label="Real BTCUSDT price (rescaled)", color="tab:blue", linewidth=2)
    ax.plot(mm_metrics.mid_prices, label="MarketMaker book mid", color="tab:orange", alpha=0.8)
    ax.plot(as_metrics.mid_prices, label="AvellanedaStoikov book mid", color="tab:green", alpha=0.8)
    ax.set_xlabel("Step (1 real minute each)")
    ax.set_ylabel("Price (rescaled)")
    ax.set_title("Simulated book mid tracking a real, exogenous price path")
    ax.legend()
    fig.tight_layout()
    fig.savefig(save_path)
    return fig


def mean_abs_deviation(prices: List[float], mid_prices: List[float]) -> float:
    """how far on average a book's mid strayed from the real anchor it was quoting
    against"""
    return sum(abs(m - p) for m, p in zip(mid_prices, prices)) / len(prices)


def plot_pnl_comparison(
    mm_history: PnLHistory, as_history: PnLHistory, save_path: str = "images/historical_backtest_pnl.png"
) -> Figure:
    fig, axes = plt.subplots(2, 1, figsize=(10, 9), sharex=True)
    for ax, history, title in (
        (axes[0], mm_history, "MarketMaker (linear vol/skew heuristic)"),
        (axes[1], as_history, "AvellanedaStoikovMarketMaker"),
    ):
        ax.plot(history.spread_pnl, label="Spread P&L", color="tab:blue")
        ax.plot(history.inventory_pnl, label="Inventory P&L", color="tab:red")
        ax.plot(history.total_pnl, label="Total P&L", linestyle="--", color="black")
        ax.axhline(0, color="grey", linewidth=0.8)
        ax.set_ylabel("P&L")
        ax.set_title(title)
        ax.legend()
    axes[1].set_xlabel("Step")
    fig.tight_layout()
    fig.savefig(save_path)
    return fig


if __name__ == "__main__":
    raw_prices = load_price_series(DATA_PATH)[:STEPS]
    prices = rescale_to_sim_scale(raw_prices)

    mm, mm_metrics, mm_pnl = run_market_maker(prices)
    as_mm, as_metrics, as_pnl = run_avellaneda_stoikov(prices)

    print(f"Backtest: {len(prices)} steps of real BTCUSDT 1-minute closes ({DATA_PATH})\n")
    print(
        f"MarketMaker:                 spread_pnl={mm.spread_pnl:.2f}, "
        f"inventory_pnl={mm_pnl.inventory_pnl[-1]:.2f}, total={mm_pnl.total_pnl[-1]:.2f}"
    )
    print(
        f"AvellanedaStoikovMarketMaker: spread_pnl={as_mm.spread_pnl:.2f}, "
        f"inventory_pnl={as_pnl.inventory_pnl[-1]:.2f}, total={as_pnl.total_pnl[-1]:.2f}"
    )

    mm_deviation = mean_abs_deviation(prices, mm_metrics.mid_prices)
    as_deviation = mean_abs_deviation(prices, as_metrics.mid_prices)
    print(
        f"\nMean |book mid - real anchor|: MarketMaker={mm_deviation:.3f}, "
        f"AvellanedaStoikov={as_deviation:.3f}"
    )

    plot_price_tracking(prices, mm_metrics, as_metrics)
    print("\nSaved images/historical_backtest_price.png")

    plot_pnl_comparison(mm_pnl, as_pnl)
    print("Saved images/historical_backtest_pnl.png")
