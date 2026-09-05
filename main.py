# main.py

from lob.book import LimitOrderBook

from simulator.random_flow import simulate_random_flow
from simulator.market_maker import MarketMaker
from simulator.imbalance_trader import ImbalanceTrader
from metrics.depth_history import DepthHistory
from metrics.pnl_history import PnLHistory


"""note: this is a simple demo script to show how to run a simulation and plot metrics.
for more sophisticated analysis, see the scripts in the analysis/ folder, which sweep parameters,
and use GBM or historical price paths rather than the random flow used here."""

def main():
    book = LimitOrderBook()

    print("simulating random market")

    mm = MarketMaker(spread=2, size=5, max_inventory=50)
    it = ImbalanceTrader(threshold=0.4, size=5, max_inventory=50)
    depth_history = DepthHistory()
    pnl_history = PnLHistory()
    metrics = simulate_random_flow(
        book,
        steps=500,
        sleep=0,
        market_maker=mm,
        imbalance_trader=it,
        depth_history=depth_history,
        pnl_history=pnl_history,
    )

    print(
        f"market maker: inventory={mm.inventory}, cash={mm.cash:.2f}, "
        f"mark_to_market={mm.mark_to_market(book):.2f} "
        f"(spread_pnl={mm.spread_pnl:.2f}, inventory_pnl={mm.inventory_pnl(book):.2f})"
    )
    print(
        f"imbalance trader: inventory={it.inventory}, cash={it.cash:.2f}, "
        f"mark_to_market={it.mark_to_market(book):.2f}"
    )

    metrics.plot(save_path="images/simulation.png")
    print("Saved metrics plot to images/simulation.png")

    depth_history.plot(save_path="images/depth_heatmap.png")
    print("Saved depth heatmap to images/depth_heatmap.png")

    pnl_history.plot(save_path="images/pnl_breakdown.png")
    print("Saved P&L breakdown plot to images/pnl_breakdown.png")


if __name__ == "__main__":
    main()
