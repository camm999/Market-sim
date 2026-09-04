# Market Sim

![Tests](https://github.com/camm999/Market-sim/actions/workflows/tests.yml/badge.svg)

A python made limit order book written from scratch, features below. All confirmed by a pytest suite and mypy checking the engine.

## Features (see commits for updates on these)

- **Matching engine** (`lob/book.py`) — limit and market orders, price-time priority, partial fills, cancellation. Best bid/ask lookup is heap-based (`O(log n)` amortized) rather than scanning every price level, see **Performance** below.
- **Random order flow** (`simulator/random_flow.py`) — Poisson arrivals of random limit/market orders around the mid price allows simulated 'live' market
- **Linear Heuristic Market maker** (`simulator/market_maker.py`) — Quotes a bid and ask around mid every step and tracks its own inventory/cash. It also skews its quotes against inventory to manage risk, and widens its spread with recent realized volatility, rolling standard deviation of *trade prices*, i.e it quotes tighter in a calm market and pulls back in a choppy one
- **Imbalance trader** (`simulator/imbalance_trader.py`) — An opposing agent that trades *with* the book's imbalance instead of personal inventory.
- **Informed trader** (`simulator/informed_trader.py`) — Given a schedule of future price-drift windows and actively trades during these windows when active. This mimics competitors in the market who may have an edge. Also gives the market direction, rather than noise from flows.
- **Metrics** (`metrics/metrics.py`) — tracks the mid price, spread, depth, and order book imbalance over a given run, and plots them, used for analysis.
- **GBM-anchored tuning** (`simulator/gbm_flow.py`) — generates a synthetic exogenous price path per seed (GARCH(1,1) variance process, Student-t innovations fat tails and volatility clustering calibrated off `data/btcusdt_1m.csv`), reused by `compare_strategies.py`/`tune_market_maker.py`/`tune_avellaneda_stoikov.py` so grid sweeps aren't scored against a price their own agent's quotes helped produce. Also generates a scheduled-drift variant for `stress_test_market_maker.py`/`avellaneda_stoikov_demo.py`, with drift switched on only during `InformedTrader`'s own known windows.
- **Depth heatmap** (`metrics/depth_history.py`) — records resting size at every price level to the relative mid, at that step, it then outputs an L2 heatmap.
- **P&L breakdown** (`metrics/pnl_history.py`) —  Splits `MarketMaker`'s P&L into spread P&L and inventory P&L, reveals impact of informed flow trader windows on the market maker.
- **Tests** (`tests/`) — pytest unit tests all code files.
- **Benchmarks** (`benchmarks/`) — measures look-up speeds investigated.
- **Strategy comparison** (`analysis/compare_strategies.py`) — statistically compares `MarketMaker` vs `ImbalanceTrader` P&L via averaging across seeds.
- **Market maker tuning** (`analysis/tune_market_maker.py`) — sweeps `MarketMaker`'s `spread`/`max_inventory` across a grid to evaluate on the above outcome. **No informed trader**
- **Adverse selection stress test** (`analysis/stress_test_market_maker.py`) — runs `MarketMaker` against the `InformedTrader` with known future drift windows,plots show inventory P&L hit and a grid sweep to see impact of volatility widening and turning inventory skew on/off.
- **Avellaneda-Stoikov market maker** (`simulator/avellaneda_stoikov.py`) — A second market making agent following the strategy given in the paper 'High Frequency Trading in a Limit Order Book' (2008), recommended read, this gives the agent a reservation price derived from inventory, risk aversion, variance, and time-to-horizon instead of `MarketMaker`'s hand-tuned linear heuristic.
- **Avellaneda-Stoikov comparison** (`analysis/avellaneda_stoikov_demo.py`) — runs both market makers through the *same* informed-trader stress scenario and tracks P&L as well as the reservation price/half-spread compressing toward the trading horizon.
- **Avellaneda-Stoikov tuning** (`analysis/tune_avellaneda_stoikov.py`) — Optimises parameters for this agent sweeping `gamma`/`k` across a grid instead, since they don't map onto the same axes as `MarketMaker`'s. **No informed trader**
- **Interactive dashboard** (`streamlit_app.py`) — a Streamlit UI over the same simulation code, so parameters like `spread`/`max_inventory`/`gamma`/`k` can be changed, allows for model tweaking and testing results above.
- **Real historical data backtest** (`simulator/historical_flow.py`, `analysis/historical_backtest.py`) — anchors synthetic order flow to a real BTCUSDT price series instead of a random walk, so fair-value is imposed externally and none of the agents can influence it.

## Project structure

```
market_sim/
├── lob/
│   └── book.py                  # core order book: Order, LimitOrderBook
├── simulator/
│   ├── random_flow.py           # random order flow generator
│   ├── market_maker.py          # market-making agent
│   ├── imbalance_trader.py      # imbalance-following agent
│   ├── informed_trader.py       # scheduled-drift agent for adverse-selection testing
│   ├── avellaneda_stoikov.py    # Avellaneda-Stoikov optimal-quoting market maker
│   ├── historical_flow.py       # order flow anchored to a real historical price series
│   └── gbm_flow.py              # synthetic exogenous price path generator (GARCH(1,1)/Student-t GBM)
├── metrics/
│   ├── metrics.py                # metrics tracking + plotting
│   ├── depth_history.py         # per-step depth snapshots + heatmap
│   └── pnl_history.py           # spread vs. inventory P&L tracking + plotting
├── tests/
│   ├── test_book.py             
│   ├── test_market_maker.py
│   ├── test_imbalance_trader.py
│   ├── test_informed_trader.py
│   ├── test_avellaneda_stoikov.py
│   ├── test_depth_history.py
│   ├── test_pnl_history.py
│   ├── test_compare_strategies.py
│   ├── test_tune_market_maker.py
│   ├── test_tune_avellaneda_stoikov.py
│   ├── test_stress_test_market_maker.py
│   ├── test_historical_flow.py
│   └── test_gbm_flow.py
├── benchmarks/
│   └── bench_best_price.py      # best bid/ask lookup benchmark
├── analysis/
│   ├── compare_strategies.py         # multi-seed strategy comparison
│   ├── tune_market_maker.py          # market maker parameter sweep
│   ├── tune_avellaneda_stoikov.py    # Avellaneda-Stoikov gamma/k sweep
│   ├── stress_test_market_maker.py   # informed-trader adverse-selection stress test
│   ├── avellaneda_stoikov_demo.py    # heuristic vs. Avellaneda-Stoikov comparison
│   └── historical_backtest.py        # real-data backtest, both market makers
├── data/
│   └── btcusdt_1m.csv            # real BTCUSDT 1-minute closes (Binance), for the historical backtest
├── images/                       # generated charts (all scripts above save here)
├── main.py                       # demo entry point
├── streamlit_app.py              # interactive dashboard
├── requirements.txt
└── diary.md                      # dev log
```

## Quickstart

```bash
git clone <your-repo-url>
cd market_sim
pip install -r requirements.txt
python main.py
```

`main.py` runs a short manual demo; a 500-step random-flow simulation with both agents active, saving a chart of mid price / spread / imbalance to `images/simulation.png` and a depth heatmap to `images/depth_heatmap.png`. 

## Interactive dashboard - See Streamlit in Analysis.md

```bash
streamlit run streamlit_app.py
```


## Running tests

```bash
python -m pytest -v
python -m mypy lob simulator metrics analysis --ignore-missing-imports --explicit-package-bases
```

## How the order book works


The `LimitOrderBook` lists all outstanding buy orders *(bids)* and sell orders *(asks)* for an asset, sorted by price. The highest bid and lowest ask (`_best_bid()`/`_best_ask()`) form the top of book and their gap is the bid-ask spread. If an order is added (`add_limit_order()`) and its price crosses the spread (i.e., it's **marketable**), it trades immediately against the best-priced opposing orders (via `_match_buy()`/`_match_sell()`). Matching follows price-time priority, better prices go first, and out of these best prices, whoever arrived first gets filled first. Any unfilled portion of an order just gets added to the book to wait for a match. Users can also cancel unfilled orders.

## How the market maker works

  
The market maker posts a bid and ask *around the current price*, earning the *spread* on round trips **instead** of betting on direction. Every fill builds up **inventory risk**, so it skews its quotes to **lean back** toward flat, long implies lower quotes and short implies higher quotes, also has max inventory limit. The spread width is recalculated each step from **recent price volatility**. Wider spreads in volatile conditions **protect** against getting picked off by stale quotes and compensate for the extra inventory risk. Because inventory skew scales with that same spread, higher volatility also amplifies the skew, not a bug. Thus, Calmer markets get tighter quotes, choppier ones get wider quotes.

## How the imbalance trader works

This agent leans with the **book's imbalance**. When there's much more resting size on the bid than the ask, that pressure often precedes the price getting pushed up, so it hits the market with a buy to ride that move, vice versa for more ask's than bid's

## Market Makers

We currently have the linear heruistic market maker (the one described above) and we are going to introduce Avellenda Stoikov below.

### Limitations of the linear heuristic

`vol_coef` and `skew_coef` are hand-picked, empirically tuned constants, not derived from anything. Its okay as a first try, but soon we will address these limitations by utilising a published research paper. 

- **No time horizon.** `MarketMaker` no notion of heavy risk aversion as session comes to an end.
- **Volatility is estimated from price levels, not increments.** `_realized_volatility` is the stdev of recent trade *prices*, meant to track the size of the random step not how far the level has drifted from where it started.
- **Inventory skew is capped by construction.** `skew_coef * (inventory / max_inventory) * half` can never exceed half the spread, the cap falls out of the formula's shape, not deliberate.
- **No explicit risk-aversion parameter.** "hatred for carrying inventory" has no dedicated measure,  it's folded into `skew_coef` with little to no meaning attached.
- **The base spread has no market-microstructure grounding.** The fixed `spread` constant isn't tied to any model of how counterparty order-arrival likelihood falls off with quote distance; it's just picked.


### Avellaneda-Stoikov market maker

`simulator/avellaneda_stoikov.py` implements the actual Avellaneda-Stoikov (2008) optimal-quoting model instead of the linear heuristic above. At each step it computes a *reservation price* i.e the price it would be indifferent to trading at given its inventory, risk aversion (`gamma`), recent price variance, and how much of a trading horizon (`total_steps`) remains and quotes a spread around that reservation price, using the following formulae:

```
reservation = mid - inventory * gamma * sigma^2 * time_remaining
spread      = gamma * sigma^2 * time_remaining + (2 / gamma) * ln(1 + gamma / k)
```
We can see a few advantages listed previously compared to the previous model limitations.

- an explicit `total_steps`/`t` horizon
- formula derived from inventory, risk aversion, variance, and time-to-horizon replaces the two independently-tuned knobs, fixing the second.
- a proper increment-based variance estimator fixes the third
- the reservation-price skew `q·γ·σ²·(T-t)` falls out of the math rather than being capped, fixing the fourth
- an explicit `gamma` parameter fixes the fifth
-  the `k` driven floor term ties the spread to a model of order-arrival decay, fixing the sixth. though `gamma` and `k` are still hand-picked for this toy sim rather than calibrated to real market data we adress this issue later.

### Bug found and fixed

The Avellaneda-Stoikov (2008) paper assumes the market maker is a small player whose own quotes can't move the mid-price, price has its own path.

-  Inventory builds up to a moderate size, and realized volatility ticks up (nothing artificial — just normal price noise).
-  Inventory skew (skew_shift in avellaneda_stoikov.py:125) pushes the reservation price tens of units away from mid.
-  That skewed quote is far enough from fair value that it gets hit immediately.
-  That trade is now a large price jump in the trade tape, which feeds into next step's _price_increment_variance (avellaneda_stoikov.py:99) — the sigma² estimate — pushing the next quote out even further.
-  That's a positive feedback loop: bigger skew → gets hit → bigger price jump → bigger variance estimate → bigger skew.

Fix-

- `max_variance_term` (`avellaneda_stoikov.py`:121) caps how much the variance term (`gamma * sigma² * time_remaining`) can grow in a single step,
- `skew_shift` is clamped to at most half the spread (`avellaneda_stoikov.py`:126) — meaning inventory skew can pull a quote all the way to fair value (reservation = mid, effectively) but never push it through fair value to the other side.

### Issues with model

- Assumes a market maker that can't move its own mid-price 
- Is calibrated with hand-picked, uncalibrated gamma/k rather than real market data, so the results says more about this sim's specific order-flow model and toy parameter choices than about the strategy itself.


### Where the P&L actually comes from 

`MarketMaker` splits its P&L into two running totals that always sum to the total mark to market/P&L:

- **`spread_pnl`** — Selling above that mid or buying below it is pure liquidity-provision profit, independent of whatever the price does afterwards.
- **`inventory_pnl(book)`** — everything else: the mark-to-market gain or loss on whatever's been carried since each fill, as fair value has drifted since then. This is the cost of holding directional risk instead of staying flat.

`metrics/pnl_history.py` (`PnLHistory`) records these, run from main.

![P&L breakdown](images/pnl_breakdown.png)

In this run, spread_pnl rises steadily, the market maker reliably earns money just from quoting, while inventory_pnl keeps getting worse. This shows the market maker doing its core job well (capturing the spread) but losing money on the side effect (holding inventory during price trends), present issue of max inventory in trending markets again. 

## Performance

`_best_bid()`/`_best_ask()` used to scan every resting price level with `max()`/`min()` on every call, `O(n)` in the number of price levels. Now they are  backed by a heap, see below file, which keeps lookups `O(log n)` amortized regardless of how many levels are resting.

```bash
python benchmarks/bench_best_price.py
```

```
  levels    dict max()     heap peek   speedup
      10        1.32ms        0.40ms      3.3x
     100        6.61ms        0.34ms     19.4x
    1000       60.36ms        0.35ms    174.4x
   10000      475.84ms        0.24ms   1987.7x
   50000     2864.49ms        0.27ms  10423.9x
```

## Results & further analysis

The tuning sweeps, adverse-selection stress test, GARCH-GBM calibration, real BTCUSDT backtest, and Streamlit walkthrough now live in [ANALYSIS.md](ANALYSIS.md), along with the closing writeup on why `MarketMaker` beats `AvellanedaStoikovMarketMaker` throughout this project.
