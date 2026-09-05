# metrics/metrics.py
from typing import List, Optional

from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from lob.book import LimitOrderBook


class Metrics:
    def __init__(self) -> None:
        self.mid_prices: List[float] = []  # mid_price() always returns a float, never None
        self.spreads: List[Optional[float]] = []
        self.bid_depths: List[int] = []
        self.ask_depths: List[int] = []
        self.total_depths: List[int] = []
        self.imbalances: List[float] = []
        self.trade_prices: List[float] = []
        self.trade_sizes: List[int] = []
        self._trades_seen = 0

    def update(self, book: LimitOrderBook) -> None:
        """extract metrics from the current state of the LOB."""

        mid = book.mid_price()
        self.mid_prices.append(mid)

        spread = book.spread()
        self.spreads.append(spread)

        # Depth (running totals on the book, so this is O(1) rather than a full walk each step)
        bid_depth = book.bid_depth()
        ask_depth = book.ask_depth()

        self.bid_depths.append(bid_depth)
        self.ask_depths.append(ask_depth)
        self.total_depths.append(bid_depth + ask_depth)

        # Imbalance
        self.imbalances.append(book.imbalance())

        # Pick up any trades that happened since the last update
        new_trades = book.trades[self._trades_seen :]
        for price, size in new_trades:
            self.record_trade(price, size)
        self._trades_seen = len(book.trades)

    def record_trade(self, price: float, size: int) -> None:
        """record trade events."""
        self.trade_prices.append(price)
        self.trade_sizes.append(size)

    def plot(self, save_path: Optional[str] = None) -> Figure:
        """plot mid-price, spread and imbalance over the simulation."""

        fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)

        axes[0].plot(self.mid_prices)
        axes[0].set_ylabel("Mid price")

        axes[1].plot(self.spreads)
        axes[1].set_ylabel("Spread")

        axes[2].plot(self.imbalances)
        axes[2].set_ylabel("Imbalance")
        axes[2].set_xlabel("Step")

        fig.tight_layout()

        if save_path:
            fig.savefig(save_path)
        else:
            plt.show()

        return fig
