# analysis/harness.py
"""
the one run-a-simulation routine every script in analysis/ shares.

each of compare_strategies / tune_market_maker / tune_avellaneda_stoikov /
stress_test_market_maker / avellaneda_stoikov_demo / historical_backtest used
to carry its own near-identical copy of "seed, build a book, build the agents,
silence the progress printing, simulate, read the P&L off the end". They are
all variations on one experiment, so the setup lives here once and each script
is left holding only the part that actually differs.

it also fixes reproducibility properly: each run gets its own
`random.Random(seed)` rather than reseeding the module-global generator, so a
run's result depends on nothing but its own seed.
"""

import contextlib
import io
import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from lob.book import LimitOrderBook, Side
from metrics.metrics import Metrics
from metrics.pnl_history import PnLHistory
from simulator.historical_flow import simulate_historical_flow
from simulator.imbalance_trader import ImbalanceTrader
from simulator.informed_trader import InformedTrader
from simulator.market_maker import MarketMaker

# the background agent every script holds fixed while it varies something else
DEFAULT_THRESHOLD = 0.4
DEFAULT_SIZE = 5
DEFAULT_MAX_INVENTORY = 50


@dataclass
class SimulationRun:
    """everything a run produced, so callers can pull out whichever part they plot."""

    book: LimitOrderBook
    market_maker: MarketMaker
    metrics: Metrics
    pnl_history: PnLHistory
    imbalance_trader: Optional[ImbalanceTrader] = None
    informed_trader: Optional[InformedTrader] = None

    @property
    def pnl(self) -> float:
        """the market maker's final mark-to-market."""
        return self.market_maker.mark_to_market(self.book)


def default_imbalance_trader() -> ImbalanceTrader:
    return ImbalanceTrader(
        threshold=DEFAULT_THRESHOLD, size=DEFAULT_SIZE, max_inventory=DEFAULT_MAX_INVENTORY
    )


def run_simulation(
    prices: Sequence[float],
    seed: int,
    market_maker: MarketMaker,
    imbalance_trader: Optional[ImbalanceTrader] = None,
    informed_trader: Optional[InformedTrader] = None,
) -> SimulationRun:
    """run one market maker against `prices` under `seed`.

    `prices` is the exogenous fair-value path (see ANALYSIS.md's "Important
    Pricing Issue")
    """
    book = LimitOrderBook()
    metrics = Metrics()
    pnl_history = PnLHistory()

    with contextlib.redirect_stdout(io.StringIO()):  # simulate_historical_flow prints progress, silence it here
        simulate_historical_flow(
            book,
            prices,
            market_maker=market_maker,
            imbalance_trader=imbalance_trader,
            informed_trader=informed_trader,
            metrics=metrics,
            pnl_history=pnl_history,
            rng=random.Random(seed),
        )

    return SimulationRun(
        book=book,
        market_maker=market_maker,
        metrics=metrics,
        pnl_history=pnl_history,
        imbalance_trader=imbalance_trader,
        informed_trader=informed_trader,
    )


def informed_trader_for(schedule: List[Tuple[int, int, Side]], size: int = 4) -> InformedTrader:
    """the adverse-selection counterparty, fed the same schedule that drives the price path."""
    return InformedTrader(schedule=schedule, size=size)
