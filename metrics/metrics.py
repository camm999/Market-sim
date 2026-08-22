# metrics/metrics.py
import matplotlib.pyplot as plt

class Metrics:
    def __init__(self):
        self.mid_prices = []
        self.spreads = []
        self.bid_depths = []
        self.ask_depths = []
        self.total_depths = []
        self.imbalances = []
        self.trade_prices = []
        self.trade_sizes = []
        self._trades_seen = 0

    def update(self, book):
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
        new_trades = book.trades[self._trades_seen:]
        for price, size in new_trades:
            self.record_trade(price, size)
        self._trades_seen = len(book.trades)

    def record_trade(self, price, size):
        """Record trade events."""
        self.trade_prices.append(price)
        self.trade_sizes.append(size)

    def plot(self, save_path=None):
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
