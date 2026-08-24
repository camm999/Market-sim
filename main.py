# main.py

from lob.book import LimitOrderBook, Order

from simulator.random_flow import simulate_random_flow
from simulator.market_maker import MarketMaker
from simulator.imbalance_trader import ImbalanceTrader
from metrics.depth_history import DepthHistory


def main():
    book = LimitOrderBook()

    # Add some limit orders
    book.add_limit_order(Order(order_id=1, side="buy", price=99, size=10))
    book.add_limit_order(Order(order_id=2, side="buy", price=100, size=5))
    book.add_limit_order(Order(order_id=3, side="sell", price=101, size=7))
    book.add_limit_order(Order(order_id=4, side="sell", price=102, size=4))

    print("Initial snapshot:")
    print(book.snapshot())

    book.add_limit_order(Order(order_id=5, side="buy", price=103, size=6))

    print("after 1st buy")
    print(book.snapshot())

    book.add_limit_order(Order(order_id=6, side="sell", price=97, size=2))
    print("after 1st sell")
    print(book.snapshot())

    book.add_limit_order(Order(order_id=7, side="sell", price=102, size=5))

    print("after 2nd sell")
    print(book.snapshot())

    book.add_market_order(side="buy", size=12)
    print("after market buy")
    print(book.snapshot())

    book.add_market_order(side="sell", size=8)
    print("after market sell")
    print(book.snapshot())

    book.cancel_order(order_id=1)

    print("after cancelling '99 buy 10'")
    print(book.snapshot())

    print("simulating random market")

    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    it = ImbalanceTrader(threshold=0.4, size=5, max_inventory=50)
    depth_history = DepthHistory()
    metrics = simulate_random_flow(
        book,
        steps=500,
        sleep=0.01,
        market_maker=mm,
        imbalance_trader=it,
        depth_history=depth_history,
    )

    print(
        f"market maker: inventory={mm.inventory}, cash={mm.cash:.2f}, "
        f"mark_to_market={mm.mark_to_market(book):.2f}"
    )
    print(
        f"imbalance trader: inventory={it.inventory}, cash={it.cash:.2f}, "
        f"mark_to_market={it.mark_to_market(book):.2f}"
    )

    metrics.plot(save_path="simulation.png")
    print("Saved metrics plot to simulation.png")

    depth_history.plot(save_path="depth_heatmap.png")
    print("Saved depth heatmap to depth_heatmap.png")


if __name__ == "__main__":
    main()
