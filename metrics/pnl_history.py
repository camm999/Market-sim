# metrics/pnl_history.py
"""tracks a market maker's P&L, split into spread capture vs. inventory risk, over time."""

from typing import List, Optional

from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from lob.book import LimitOrderBook
from simulator.market_maker import MarketMaker


class PnLHistory:
    """
    splits mark to market into spread P&L and inventory P&L.

    spread P&L + inventory P&L == total P&L at every step. Plotting them
    separately shows where a run's result genuinely came from.

    also records raw `inventory` size each step, so a
    caller can measure how fast a position mean-reverts back toward flat
    after a shock, independent of what price did while it was open.
    """

    def __init__(self) -> None:
        self.spread_pnl: List[float] = []
        self.inventory_pnl: List[float] = []
        self.total_pnl: List[float] = []
        self.inventory: List[int] = []

    def update(self, market_maker: MarketMaker, book: LimitOrderBook) -> None:
        spread = market_maker.spread_pnl
        total = market_maker.mark_to_market(book)
        self.spread_pnl.append(spread)
        self.inventory_pnl.append(total - spread)
        self.total_pnl.append(total)
        self.inventory.append(market_maker.inventory)

    def plot(self, save_path: Optional[str] = None) -> Figure:
        """plot spread P&L, inventory P&L, and their total over the run."""
        fig, ax = plt.subplots(figsize=(10, 5))

        ax.plot(self.spread_pnl, label="Spread P&L")
        ax.plot(self.inventory_pnl, label="Inventory P&L")
        ax.plot(self.total_pnl, label="Total P&L", linestyle="--", color="black")
        ax.axhline(0, color="grey", linewidth=0.8)
        ax.set_xlabel("Step")
        ax.set_ylabel("P&L")
        ax.set_title("Market maker P&L: spread capture vs. inventory risk")
        ax.legend()
        fig.tight_layout()

        if save_path:
            fig.savefig(save_path)
        else:
            plt.show()

        return fig
