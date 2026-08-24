# metrics/depth_history.py
"""Records order book depth over time and renders it as an L2-style heatmap."""

from typing import List, Optional

import numpy as np
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from lob.book import LimitOrderBook


class DepthHistory:
    """
    Tracks resting size at each price level, relative to the mid price, at
    every step of a simulation. Unlike Metrics (which tracks scalar summary
    stats like total depth), this keeps a full per-level snapshot each step
    so it can be rendered as a heatmap of the book's shape over time.

    Prices are stored as an *offset from mid* rather than an absolute price,
    since mid drifts over a run (random walk) - a fixed absolute price grid
    would either be wastefully wide or miss levels once price has moved.
    Offsets outside +/-offset_range are dropped; the default is wide enough
    to hold everything this project's agents actually quote at.
    """

    def __init__(self, offset_range: int = 12) -> None:
        self.offset_range = offset_range
        self.frames: List[np.ndarray] = []

    def update(self, book: LimitOrderBook) -> None:
        """Snapshot resting depth by price offset from mid. Bids are stored
        as positive size, asks as negative size, so a single heatmap can
        show both sides with a diverging (green/red) colormap."""
        mid = book.mid_price()
        width = 2 * self.offset_range + 1
        frame = np.zeros(width)

        for price, queue in book.bids.items():
            offset = round(price - mid)
            if -self.offset_range <= offset <= self.offset_range:
                frame[offset + self.offset_range] += sum(o.size for o in queue)

        for price, queue in book.asks.items():
            offset = round(price - mid)
            if -self.offset_range <= offset <= self.offset_range:
                frame[offset + self.offset_range] -= sum(o.size for o in queue)

        self.frames.append(frame)

    def plot(self, save_path: Optional[str] = None) -> Figure:
        """Render the recorded frames as a time x price-offset heatmap."""
        data = np.array(self.frames).T  # rows: price offset, columns: step

        fig, ax = plt.subplots(figsize=(12, 6))
        vmax = np.abs(data).max() or 1  # avoid a zero-width color range on an empty book

        im = ax.imshow(
            data,
            aspect="auto",
            origin="lower",
            cmap="RdYlGn",
            vmin=-vmax,
            vmax=vmax,
            extent=(0, data.shape[1], -self.offset_range, self.offset_range),
        )
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--")  # the mid price line
        ax.set_xlabel("Step")
        ax.set_ylabel("Price offset from mid")
        ax.set_title("Order book depth over time (green = bid, red = ask)")
        fig.colorbar(im, ax=ax, label="Resting size (signed)")
        fig.tight_layout()

        if save_path:
            fig.savefig(save_path)
        else:
            plt.show()

        return fig
