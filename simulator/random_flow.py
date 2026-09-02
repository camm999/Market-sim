from typing import Optional
from lob.book import LimitOrderBook, Order, Side
from metrics.metrics import Metrics
from metrics.depth_history import DepthHistory
from metrics.pnl_history import PnLHistory
from simulator.market_maker import MarketMaker
from simulator.imbalance_trader import ImbalanceTrader
from simulator.informed_trader import InformedTrader
import random
import time


def random_limit_order(book: LimitOrderBook, order_id: int) -> Order:
    """generate a random limit order around the mid price."""
    side: Side = random.choice(["buy", "sell"])
    size = random.randint(1, 10)

    mid = book.mid_price()
    if mid is None:
        mid = 100  # initial mid price if book is empty

    # price distribution: small random deviation around mid
    price = mid + random.randint(-3, 3)

    return Order(order_id, side, price, size)



def random_market_order(book: LimitOrderBook) -> None:
    side: Side = random.choice(["buy", "sell"])
    size = random.randint(1, 10)
    book.add_market_order(side, size)


def simulate_random_flow(
    book: LimitOrderBook,
    steps: int = 500,
    lambda_limit: float = 0.7,
    lambda_market: float = 0.3,
    sleep: float = 0.1,
    metrics: Optional[Metrics] = None,
    market_maker: Optional[MarketMaker] = None,
    imbalance_trader: Optional[ImbalanceTrader] = None,
    informed_trader: Optional[InformedTrader] = None,
    depth_history: Optional[DepthHistory] = None,
    pnl_history: Optional[PnLHistory] = None,
) -> Metrics:
    """
    simulates random order flow using Poisson arrivals.
    lambda_limit: probability of a limit order arrival
    lambda_market: probability of a market order arrival
    sleep: seconds to wait between steps (set to 0 for instant runs)
    lists metrics, agents, and optional history trackers to update each step.
    
    """

    if metrics is None:
        metrics = Metrics()

    order_id = 1

    for t in range(steps):

        if market_maker is not None:
            market_maker.quote(book)

        if imbalance_trader is not None:
            imbalance_trader.act(book)

        if informed_trader is not None:
            informed_trader.act(book)

        # poisson arrival decides what type of order arrives
        r = random.random()

        if r < lambda_limit:
            # generate and add a random limit order
            order = random_limit_order(book, order_id)
            book.add_limit_order(order)
            order_id += 1

        elif r < lambda_limit + lambda_market:
            # generate a random market order
            random_market_order(book)

        metrics.update(book)

        if depth_history is not None:
            depth_history.update(book)

        if pnl_history is not None and market_maker is not None:
            pnl_history.update(market_maker, book)

        # optional, print mid price every step
        if t % 50 == 0:
            print(f"t={t}, mid={book.mid_price()}, spread={book.spread()}")

        if sleep:
            time.sleep(sleep)

    return metrics
