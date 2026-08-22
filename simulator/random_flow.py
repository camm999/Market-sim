from collections import deque
from lob.book import LimitOrderBook, Order
from metrics.metrics import Metrics
import random
import time
import numpy as np



def random_limit_order(book, order_id):
        """Generate a random limit order around the mid price."""
        side = random.choice(["buy", "sell"])
        size = random.randint(1, 10)

        mid = book.mid_price()
        if mid is None:
            mid = 100  # initial mid price if book is empty

        # Price distribution: small random deviation around mid
        price = mid + random.randint(-3, 3)

        return Order(order_id, side, price, size)

#market 
def random_market_order(book):
        side = random.choice(["buy", "sell"])
        size = random.randint(1, 10)
        book.add_market_order(side, size)

    

def simulate_random_flow(book, steps=500, lambda_limit=0.7, lambda_market=0.3, sleep=0.1, metrics=None, market_maker=None):
        """
        Simulate random order flow using Poisson arrivals.
        lambda_limit: probability of a limit order arrival
        lambda_market: probability of a market order arrival
        sleep: seconds to wait between steps (set to 0 for instant runs)
        metrics: optional Metrics instance to record into; created if not passed
        market_maker: optional MarketMaker that re-quotes around mid every step
        """

        if metrics is None:
            metrics = Metrics()

        order_id = 1

        for t in range(steps):

            if market_maker is not None:
                market_maker.quote(book)

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