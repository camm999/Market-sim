# simulator/historical_flow.py
"""
replays synthetic order flow anchored to a real historical price series,
instead of simulate_random_flow's pure random walk and GBM pricing.

see the README's "Real historical data backtest" section for details.

Data: data/btcusdt_1m.csv - 1000 minutes of real BTCUSDT 1-minute close
prices from Binance's public klines endpoint (no auth required), fetched
once and committed as a static file so runs stay offline and reproducible.

"""

import csv
from typing import List, Optional, Sequence

from lob.book import LimitOrderBook, Order, Side
from metrics.depth_history import DepthHistory
from metrics.metrics import Metrics
from metrics.pnl_history import PnLHistory
from simulator.imbalance_trader import ImbalanceTrader
from simulator.informed_trader import InformedTrader
from simulator.market_maker import MarketMaker
from simulator.rng import RandomSource, resolve


def load_price_series(path: str) -> List[float]:
    """read the `close` column out of a (timestamp, close) CSV."""
    with open(path, newline="") as f:
        return [float(row["close"]) for row in csv.DictReader(f)]


def rescale_to_sim_scale(prices: Sequence[float], base: float = 100.0) -> List[float]:
    """rebase a real price series onto this sim's usual ~100-scale, by
    replaying percentage returns onto a synthetic starting
    price - preserving the real shape (drift, volatility, jump timing)
    while staying compatible with agent defaults, the same way
    simulate_random_flow's random walk does."""
    if not prices:
        return []
    rescaled = [base]
    for prev, curr in zip(prices, prices[1:]):
        pct_return = (curr - prev) / prev
        rescaled.append(rescaled[-1] * (1 + pct_return))
    return rescaled


def _historical_limit_order(anchor_price: float, order_id: int, rng: RandomSource) -> Order:
    side: Side = rng.choice(["buy", "sell"])
    size = rng.randint(1, 10)
    price = anchor_price + rng.randint(-3, 3)
    return Order(order_id, side, price, size)


def _historical_market_order(book: LimitOrderBook, rng: RandomSource) -> None:
    side: Side = rng.choice(["buy", "sell"])
    size = rng.randint(1, 10)
    book.add_market_order(side, size)


def simulate_historical_flow(
    book: LimitOrderBook,
    prices: Sequence[float],
    lambda_limit: float = 0.7,
    lambda_market: float = 0.3,
    metrics: Optional[Metrics] = None,
    market_maker: Optional[MarketMaker] = None,
    imbalance_trader: Optional[ImbalanceTrader] = None,
    informed_trader: Optional[InformedTrader] = None,
    depth_history: Optional[DepthHistory] = None,
    pnl_history: Optional[PnLHistory] = None,
    rng: Optional[RandomSource] = None,
) -> Metrics:
    """
    same per-step loop as simulate_random_flow, run for
    len(prices) steps not a chosen step count - one step per
    historical price point, in order. Each synthetic order is anchored to
    prices[t] (see rescale_to_sim_scale) rather than the book's own mid,
    so the fair-value process driving this run is real, not generated.

    rng: an explicit random.Random for a reproducible run; omitted, draws come
    from the module-global `random` as before (see simulator/rng.py).
    """
    if metrics is None:
        metrics = Metrics()
    draw = resolve(rng)

    order_id = 1

    for t, anchor in enumerate(prices):
        if market_maker is not None:
            market_maker.quote(book)

        if imbalance_trader is not None:
            imbalance_trader.act(book)

        if informed_trader is not None:
            informed_trader.act(book)

        r = draw.random()

        if r < lambda_limit:
            order = _historical_limit_order(anchor, order_id, draw)
            book.add_limit_order(order)
            order_id += 1
        elif r < lambda_limit + lambda_market:
            _historical_market_order(book, draw)

        metrics.update(book)

        if depth_history is not None:
            depth_history.update(book)

        if pnl_history is not None and market_maker is not None:
            pnl_history.update(market_maker, book)

        if t % 100 == 0:
            print(f"t={t}, anchor={anchor:.2f}, mid={book.mid_price()}, spread={book.spread()}")

    return metrics
