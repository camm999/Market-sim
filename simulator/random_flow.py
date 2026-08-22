from typing import Optional
from lob.book import LimitOrderBook, Order, Side
from metrics.metrics import Metrics
from simulator.market_maker import MarketMaker
from simulator.imbalance_trader import ImbalanceTrader
import random
import time


def random_limit_order(book: LimitOrderBook, order_id: int) -> Order:
    """Generate a random limit order around the mid price."""
    side: Side = random.choice(["buy", "sell"])
    size = random.randint(1, 10)

    mid = book.mid_price()
    if mid is None:
        mid = 100  # initial mid price if book is empty

    # Price distribution: small random deviation around mid
    price = mid + random.randint(-3, 3)

    return Order(order_id, side, price, size)


# market
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
) -> Metrics:
    """
    Simulate random order flow using Poisson arrivals.
    lambda_limit: probability of a limit order arrival
    lambda_market: probability of a market order arrival
    sleep: seconds to wait between steps (set to 0 for instant runs)
    metrics: optional Metrics instance to record into; created if not passed
    market_maker: optional MarketMaker that re-quotes around mid every step
    imbalance_trader: optional ImbalanceTrader that trades with strong imbalance
    """

    if metrics is None:
        metrics = Metrics()

    order_id = 1

    for t in range(steps):

        if market_maker is not None:
            market_maker.quote(book)

        if imbalance_trader is not None:
            imbalance_trader.act(book)

        # Poisson arrival: decide what type of order arrives
        r = random.random()

        if r < lambda_limit:
            # Generate and add a random limit order
            order = random_limit_order(book, order_id)
            book.add_limit_order(order)
            order_id += 1

        elif r < lambda_limit + lambda_market:
            # Generate a random market order
            random_market_order(book)

        metrics.update(book)

        # Optional: print mid price every step
        if t % 50 == 0:
            print(f"t={t}, mid={book.mid_price()}, spread={book.spread()}")

        if sleep:
            time.sleep(sleep)

    return metrics
