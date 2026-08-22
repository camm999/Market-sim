# metrics/metrics.py
from typing import List, Optional

from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from lob.book import LimitOrderBook


class Metrics:
    def __init__(self) -> None:
        self.mid_prices: List[Optional[float]] = []
        self.spreads: List[Optional[float]] = []
        self.bid_depths: List[int] = []
        self.ask_depths: List[int] = []
        self.total_depths: List[int] = []
        self.imbalances: List[float] = []
        self.trade_prices: List[float] = []
        self.trade_sizes: List[int] = []
        self._trades_seen = 0

    def update(self, book: LimitOrderBook) -> None:
        """Extract metrics from the current state of the LOB."""

        mid = book.mid_price()
        self.mid_prices.append(mid)

        spread = book.spread()
        self.spreads.append(spread)

        # Depth
        bid_depth = sum(sum(o.size for o in q) for q in book.bids.values())
        ask_depth = sum(sum(o.size for o in q) for q in book.asks.values())
        total_depth = bid_depth + ask_depth

        self.bid_depths.append(bid_depth)
        self.ask_depths.append(ask_depth)
        self.total_depths.append(total_depth)

        # Imbalance
        if total_depth > 0:
            imbalance = (bid_depth - ask_depth) / total_depth
        else:
            imbalance = 0
        self.imbalances.append(imbalance)

        # Pick up any trades that happened since the last update
        new_trades = book.trades[self._trades_seen :]
        for price, size in new_trades:
            self.record_trade(price, size)
        self._trades_seen = len(book.trades)

    def record_trade(self, price: float, size: int) -> None:
        """Record trade events."""
        self.trade_prices.append(price)
        self.trade_sizes.append(size)

    def plot(self, save_path: Optional[str] = None) -> Figure:
        """Plot mid-price, spread and imbalance over the simulation."""

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
