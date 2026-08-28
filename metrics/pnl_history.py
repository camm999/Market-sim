# metrics/pnl_history.py
"""Tracks a MarketMaker's P&L, split into spread capture vs. inventory risk, over time."""

from typing import List, Optional

from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from lob.book import LimitOrderBook
from simulator.market_maker import MarketMaker


class PnLHistory:
    """
    Records a MarketMaker's mark-to-market P&L every step, split into its
    two components:

    - spread P&L: the edge captured on each fill relative to the mid the
      quote was centered on at fill time — profit from providing liquidity,
      independent of where price goes afterwards.
    - inventory P&L: the mark-to-market swing on whatever's been carried
      since each fill, as fair value has moved since then.

    spread P&L + inventory P&L == total P&L at every step. Plotting them
    separately shows whether a run's result came from genuinely earning
    the spread or from getting picked off by informed flow and then riding
    the position - something the total alone can't distinguish.
    """

    def __init__(self) -> None:
        self.spread_pnl: List[float] = []
        self.inventory_pnl: List[float] = []
        self.total_pnl: List[float] = []

    def update(self, market_maker: MarketMaker, book: LimitOrderBook) -> None:
        spread = market_maker.spread_pnl
        total = market_maker.mark_to_market(book)
        self.spread_pnl.append(spread)
        self.inventory_pnl.append(total - spread)
        self.total_pnl.append(total)

    def plot(self, save_path: Optional[str] = None) -> Figure:
        """Plot spread P&L, inventory P&L, and their total over the run."""
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
