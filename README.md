# Market Sim

![Tests](https://github.com/camm999/Market-sim/actions/workflows/tests.yml/badge.svg)

A limit order book (LOB) simulator written from scratch in Python — the matching engine, random order flow, two contrasting trading agents, and metrics tracking, with a pytest suite and mypy checking the core engine.

A python made limit order book written from scratch, features below. All confirmed by a pytest suite and mypy checking the engine.

## Features (see commits for updates on these)

- **Matching engine** (`lob/book.py`) — limit and market orders, price-time priority, partial fills, cancellation. Best bid/ask lookup is heap-based (`O(log n)` amortized) rather than scanning every price level. Also has a heap-based lookup ('O(log n) amortized), see 'performance'.
- **Random order flow** (`simulator/random_flow.py`) — Poisson  arrivals of random limit/market orders around the mid price allows simulated 'live' market
- **Market maker** (`simulator/market_maker.py`) — Quotes a bid and ask around mid every step and tracks its own inventory/cash. It also skews its quotes against inventory to manage risk, and widens its spread with recent realized volatility ,rolling standard deviation of *trade prices*, i.e it quotes tighter in a calm market and pulls back in a choppy one
- **Imbalance trader** (`simulator/imbalance_trader.py`) — An opposing agent that trades *with* the book's imbalance instead of personal inventory.
- **Informed trader** (`simulator/informed_trader.py`) — Given a schedule of future price-drift windows and actively trades during these windows when active. This mimicks competitors in the market who may have an edge. Also gives the market direction, rather than noise from flows.
- **Metrics** (`metrics/metrics.py`) — tracks the mid price, spread, depth, and order book imbalance over a given run, and plots them, used for analysis.
- **GBM-anchored tuning** (`simulator/gbm_flow.py`) — generates a synthetic exogenous price path per seed (GARCH(1,1) variance process, Student-t innovations fat tails and volatility clustering calibrated off `data/btcusdt_1m.csv`), reused by `compare_strategies.py`/`tune_market_maker.py`/`tune_avellaneda_stoikov.py` so grid sweeps aren't scored against a price their own agent's quotes helped produce. Also generates a scheduled-drift variant for `stress_test_market_maker.py`/`avellaneda_stoikov_demo.py`, with drift switched on only during `InformedTrader`'s own known windows.
- **Depth heatmap** (`metrics/depth_history.py`) — records resting size at every price level to the relative mid, at that step, it then outputs an L2 heatmap.
- **P&L breakdown** (`metrics/pnl_history.py`) —  Splits `MarketMaker`'s P&L into spread P&L and inventory P&L, reveals impact of informed flow trader windows on the market maker.
- **Tests** (`tests/`) — pytest unit tests all code files.
- **Benchmarks** (`benchmarks/`) — measures look-up speeds investigated.
- **Strategy comparison** (`analysis/compare_strategies.py`) — statistically compares `MarketMaker` vs `ImbalanceTrader` P&L via averaging across seeds.
- **Market maker tuning** (`analysis/tune_market_maker.py`) — sweeps `MarketMaker`'s `spread`/`max_inventory` across a grid to evaluate on the above outcome. **No informed trader**
- **Adverse selection stress test** (`analysis/stress_test_market_maker.py`) — runs `MarketMaker` against the `InformedTrader` with known future drift windows,plots show inventory P&L hit and a grid sweep to see impact of volatility widening and turning inventory skew on/off.
- **Avellaneda-Stoikov market maker** (`simulator/avellaneda_stoikov.py`) — A second market making agent following the strategdy given in the paper 'High Frequency Trading in a Limit Order Book' (2008), recommended read, this gives the agent a reservation price derived from inventory, risk aversion, variance, and time-to-horizon instead of `MarketMaker`'s hand-tuned linear heuristic.
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

## Interactive dashboard - user explanation at bottom

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
- fixes the first a single formula derived from inventory, risk aversion, variance, and time-to-horizon replaces the two independently-tuned knobs, fixing the second
- a proper increment-based variance estimator fixes the third
- the reservation-price skew `q·γ·σ²·(T-t)` falls out of the math rather than being capped, fixing the fourth
- an explicit `gamma` parameter fixes the fifth
-  the `k` driven floor term ties the spread to a model of order-arrival decay, fixing the sixth. though `gamma` and `k` are still hand-picked for this toy sim rather than calibrated to real market data we adress this issue later.

**bug fix** 

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

## Pricing Issue  - PLEASE READ

We would like to be able to compare and analyse results from out code. One major issue is that our market makers quotes often shape the market and have a heavy influence on the mid-price.

`random_flow.py`'s synthetic limit orders anchor to `book.mid_price()` every step, and a resting market maker's own bid/ask are frequently the best bid/ask in the book, so the "market" a strategy is scored against isn't independent of the strategy itself. It results in heavy bias and creates a feedback loop, i.e `MarketMaker` quotes, that quote often sets the mid, the next synthetic order re-centers on that new mid, `MarketMaker` quotes again around it, and so on. Two consequences follow directly:

- **Tuning sweeps can crown the wrong "best" config.** A `spread`/`max_inventory` (or `gamma`/`k`) combination isn't just scored on how well it manages inventory risk against the market, it's also scored on how favourably it happens to interact with its own feedback loop. 
- **Head-to-head comparisons.** `MarketMaker` and `AvellanedaStoikovMarketMaker` quote differently, so even reseeded to the same starting seed, each shapes *its own* book's mid differently once it starts quoting

The fix used throughout the sections below is to stop letting the mid come from the book at all. `simulate_historical_flow` (`simulator/historical_flow.py`) anchors every synthetic order to an externally supplied price series instead of `book.mid_price()`, so nothing any agent does can move the price its own P&L is later measured against. That series can be a synthetic price path (`simulator/gbm_flow.py`, driftless or with drift confined to `InformedTrader`'s own known windows) or a real historical one (`data/btcusdt_1m.csv`) — either way, it's fixed before the run starts and no agent's quotes can touch it. Sections below are marked by which price process they use, so results that still run against the self-referential walk aren't mistaken for the corrected ones.

`simulator/gbm_flow.py`'s synthetic path is now GARCH(1,1) with Student-t innovations, not plain constant-volatility GBM — see "GBM Priced" below for why that changed and what it fixes.

We also include a section where we extract real historical data towards the end.

## GBM Priced (GARCH(1,1) implementation)



### Strategy comparison - Please see tuning after for explanation

`analysis/compare_strategies.py` runs the simulation across 200 independent random seeds and compares `MarketMaker`, `AvellanedaStoikovMarketMaker`, and `ImbalanceTrader` on final mark-to-market P&L. `MarketMaker` and `AvellanedaStoikovMarketMaker` each get their own simulation per seed rather than sharing one book (quotes still add shape), but both are anchored to the identical GARCH-GBM path for that seed, generated fresh per seed rather than reused across seeds.

```bash
python -m analysis.compare_strategies
```

```
200 runs, 0-199

MarketMaker        mean=  -143.20  stdev= 1482.13  min= -9461.07  max=  3297.12  profitable=102/200 ( 51.0%)
AvellanedaStoikov  mean= -1626.25  stdev= 1442.43  min= -8950.71  max=   687.59  profitable= 12/200 (  6.0%)
ImbalanceTrader    mean=  -593.73  stdev= 2215.07  min= -6975.88  max= 10963.06  profitable= 80/200 ( 40.0%)

MarketMaker beat ImbalanceTrader head-to-head in 124/200 runs (62.0%)
AvellanedaStoikov beat ImbalanceTrader head-to-head in 83/200 runs (41.5%)
AvellanedaStoikov beat MarketMaker head-to-head in 5/200 runs (2.5%)
```

The `min`/`max` columns show the fat tails directly: every agent's worst and best run got noticeably more extreme than the old plain-GBM figures (e.g. `MarketMaker`'s min went from -5406.92 to -9461.07, `ImbalanceTrader`'s max from 6171.42 to 10963.06) — the GARCH path's occasional large Student-t shocks show up as real tail P&L, not just a wider mean/stdev.



![Strategy comparison](images/strategy_comparison.png)

## Is it a Tuning Issue?  - Streamlit recomennded to test variety of parameters

### Marker Maker

`analysis/tune_market_maker.py` sweeps `MarketMaker`'s `spread` and `max_inventory` across a grid (`ImbalanceTrader` present, same as above), anchored to the same GARCH-GBM exogenous price path per seed as the strategy comparison above.

```bash
python -m analysis.tune_market_maker
```

![Market maker tuning](images/market_maker_tuning.png)

Performance rises with `spread` almost everywhere in the grid since wider quotes simply capture more per fill. The interaction with `max_inventory` flips direction as `spread` widens, at `spread=1`, a bigger inventory cap makes things steadily worse, since the extra exposure isn't compensated by a wide enough spread. The best cell is `spread=8, max_inventory=50` (mean P&L 2405.79, 92% profitable), still the widest spread in the grid, but now a *mid-sized* cap rather than the largest one. That's a genuine shift from the old plain-GBM sweep (which crowned `max_inventory=200`, the largest cap): under fat tails an occasional large shock can hit a big resting inventory much harder, so the best cap now trades off some upside against limiting exposure to that tail risk, instead of just maximizing exposure to the (previously thinner-tailed) trend.

### Avellaneda-Stoikov Market Maker

`AvellanedaStoikovMarketMaker`'s knobs (`gamma`risk aversion and `k` order-arrival decay) aren't comparable to `MarketMaker`'s (`spread`, `max_inventory`), so this gets its own sweep rather than an extra axis on the grid above. 

```bash
python -m analysis.tune_avellaneda_stoikov
```

![Avellaneda-Stoikov tuning](images/avellaneda_stoikov_tuning.png)

The default (`gamma=0.0001, k=1.5`) used previously is nowhere close to the best. Performance rises almost monotonically with `gamma` at every `k` tested. A heavily risk averse quoter skews its reservation price hard against inventory on every fill and against a price it genuinely can't influence, skew saves us. `k` matters too since `k=0.5`, the tightest order-arrival floor, outperforms every wider `k` at every `gamma` tested. The best cell is `gamma=0.001, k=0.5` (mean P&L 1438.45, 86% profitable) — the highest risk aversion and the tightest floor in the grid, the same corner as before; the fat tails and clustering lower the mean P&L somewhat (1562.08 → 1438.45) but don't change which corner wins.

The best cell comfortably clears `ImbalanceTrader`'s own mean (-593.73) from the strategy comparison above, unlike the untuned default. So the mixed/losing strategy-comparison result above is a default-tuning artifact.

I recommend the reader use the streamlit app to investigate and play with these parameters. As well as seeing the impact of a informed trader on these results.

## Adverse selection stress test

Nobody in a plain GARCH-GBM path knows where price is going next, so any adverse selection `MarketMaker` suffers there is incidental. `simulator/informed_trader.py` adds `InformedTrader`, fed a ground-truth schedule of future price-drift windows at construction, which trades a market order in that direction every step a window is active. To keep that edge the price itself carries drift only during those same windows instead. `simulator/gbm_flow.py`'s `generate_scheduled_drift_garch_gbm_path` builds a GARCH-GBM path from `InformedTrader`'s own `schedule`, drift on during the window, so the move is in the exogenous anchor not dependent on order flow.

`analysis/stress_test_market_maker.py` runs `MarketMaker` against two 50-step informed windows (a "buy" drift, then later a "sell" drift), recording `spread_pnl`/`inventory_pnl` via `PnLHistory` throughout:

```bash
python -m analysis.stress_test_market_maker
```

![Informed trader demo](images/informed_trader_demo.png)

`spread_pnl` climbs steadily throughout the run, `MarketMaker` is still earning its edge on every individual fill. `inventory_pnl` tells the opposite story, it craters right as each window opens, as `MarketMaker` keeps quoting a spread around a mid the scheduled drift is actively walking away from it. Essentially, you're buying into a rise then getting caught short into a further fall. 

### Does widening protect you? Does skew help you recover? 

Two independent parameters are available to test: `vol_coef` (widens quotes with realized volatility), `skew_coef` (multiplies the inventory-skew term; `skew_coef=0` disables it). Sweeping both across `{0, 1} × {0, 1}`, 30 seeds each, and measuring the worst `inventory_pnl` drawdown in the window, then the mean `abs|inventory|` over the 50 steps after a window ends (how close it's gotten back to flat).

```
vol_coef=0.0  skew_coef=0.0  mean_drawdown=  -967.21  mean_|inventory|_after= 46.59
vol_coef=0.0  skew_coef=1.0  mean_drawdown=  -971.36  mean_|inventory|_after= 40.25
vol_coef=1.0  skew_coef=0.0  mean_drawdown=  -846.71  mean_|inventory|_after= 46.59  <-- smallest drawdown
vol_coef=1.0  skew_coef=1.0  mean_drawdown=  -895.37  mean_|inventory|_after= 38.78  <-- fastest reversion
```

![Stress test grid](images/stress_test_grid.png)

**Skew helps mean-revert, cleanly and consistently.** Both `skew_coef=1.0` rows post a lower `mean_|inventory|_after` than the matching `skew_coef=0.0` row, regardless of `vol_coef` since skewing quotes against inventory pulls the position back toward flat faster once the drift window ends.

**Widening modestly helps drawdown at both `skew_coef` settings, and the two knobs don't fight each other.** `vol_coef=1` improves drawdown over `vol_coef=0` whether `skew_coef` is 0 (-967.21 to -846.71) or 1 (-971.36 to -895.37), a small, consistent improvement in both cases rather than a sharp interaction effect — the same qualitative finding as before the GARCH-GBM switch, with the exact numbers shifted by the added tail risk and clustering.

Informed trader always has marketable orders regardless of `MarketMaker`'s spread — widening doesn't stop it from trading, it changes *who* it trades against. A wider `MarketMaker` quote sits further from the top of book, so more of the flow gets absorbed by other resting synthetic orders instead of `MarketMaker` itself.


### Avellaneda_stoikov_demo (default)

`analysis/avellaneda_stoikov_demo.py` runs both market makers through the identical informed-trader stress scenario from the section above (same schedule, same scheduled-drift GARCH-GBM path):

```bash
python -m analysis.avellaneda_stoikov_demo
```

```
MarketMaker:                 spread_pnl=2226.74, inventory_pnl=-2264.44, total=-37.70
AvellanedaStoikovMarketMaker: spread_pnl=852.07, inventory_pnl=-2533.78, total=-1681.70
```

![Avellaneda-Stoikov comparison](images/avellaneda_stoikov_comparison.png)

`AvellanedaStoikovMarketMaker` takes a *larger* `inventory_pnl` hit here than the linear heuristic (-2533.78 vs. -2264.44) and finishes well behind it (-1681.70 vs. -37.70) — the same finding as the strategy comparison above, from a different angle. It's running at `gamma=0.0001`, the specific setting the tuning sweep above shows is the worst in the grid, not a merely suboptimal one. The model just hasn't been pointed at parameters suited to a price it has no ability to lean on.

### Is this actually high-frequency trading?

Not in any operational sense, even though the model comes from a paper titled "High-frequency trading in a limit order book" and the strategy where you continuously re-quote both sides. What this project simulates is the *strategy*, not the *speed* real HFT needs to run it profitably. Concretely, it doesn't model:


## Non GBM

## Real historical data backtest (2026-08-30, 14:21–22:40 UTC)

Everything above anchors to a synthetic GARCH-GBM price path i.e exogenous, and now shaped to carry BTCUSDT-like fat tails and volatility clustering, but still not the *actual* historical path: no genuine drift, no real jump timing, no event influence. `analysis/historical_backtest.py` swaps that for `simulator/historical_flow.py` anchored to an actual historical series instead: `data/btcusdt_1m.csv`, 1000 minutes of real BTCUSDT 1-minute close prices (no authentication required; fetched once and committed as a static CSV).

Order-level replay of genuine market microstructure (submissions, cancellations, modifications) would need a licensed feed like LOBSTER, which explicitly disallows redistributing its data, so **the fair-value process is real, the order arrivals around it are still synthetic**, generated the same way the GARCH-GBM-anchored runs above are. We expierience the actual drifts and jumps this market expierenced, not just another distribution — we are only pinned to one 1000 minute window.

Since the real series (~78,000-79,000) and the sim's usual scale (agent defaults tuned around ~100) don't match, `rescale_to_sim_scale()` rebuilds a ~100 based series by replaying the real data's actual percentage returns onto a synthetic starting price, the real shape (drift, volatility, jump timing), on a compatible scale.

```bash
python -m analysis.historical_backtest
```

```
Backtest: 500 steps of real BTCUSDT 1-minute closes (data/btcusdt_1m.csv)

MarketMaker:                 spread_pnl=919.10, inventory_pnl=-210.24, total=708.86
AvellanedaStoikovMarketMaker: spread_pnl=610.80, inventory_pnl=-283.51, total=327.28

Mean |book mid - real anchor|: MarketMaker=1.305, AvellanedaStoikov=1.041
```

![Historical backtest P&L](images/historical_backtest_pnl.png)

Both market makers finish profitable against this real window; a calm one, only a 1.32% price range across the whole 500 minutes. `MarketMaker` outperforms `AvellanedaStoikovMarketMaker` here (708.86 vs 327.28), consistent with every other default `gamma` comparison in this README (the strategy comparison, the adverse-selection demo). `AvellanedaStoikovMarketMaker`'s tuning gap isn't a synthetic-GBM artifact, it shows up against real market data too. That said, this is still one 500-minute window out of however many the market could have taken, exactly the reason `compare_strategies.py` exists to average over many scenarios instead of trusting any one run.

![Historical backtest price tracking](images/historical_backtest_price.png)

 Both books are anchored to the *identical* real price series,  any gap between the two is a direct read on which market maker's own resting quotes perturb the book furthest from the true exogenous price. There is a real, measurable, gap `AvellanedaStoikovMarketMaker` tracks the real anchor noticeably tighter than `MarketMaker` (mean `|book mid - real anchor|` 1.041 vs 1.305 — about 20% tighter — and a smaller worst-case deviation too, 3.745 vs 5.571 at this run's peak). Neither book tracks the real series' exact tick-by-tick path — both are dominated by the synthetic order-placement noise (`±3` on a ~100 base, inherited unchanged from `random_flow.py`) relative to this particular window's small real volatility (1.32% range) — but `AvellanedaStoikovMarketMaker`'s reservation-price mechanism visibly holds closer to fair value than `MarketMaker`'s linear skew does, consistent with it being the more principled model.  

## Example output from main

Running `main.py` produces `images/simulation.png` — mid price, spread, and order book imbalance over the course of the simulated run — and `images/depth_heatmap.png`, showing resting order book depth by price offset from mid over time (green = bid side, red = ask side):

![Depth heatmap](images/depth_heatmap.png)

The **Use GBM exogenous price path** toggle in `streamlit_app.py` exists for the same reason `analysis/historical_backtest.py` and the GBM-anchored sweeps do — a market maker's own quotes should never be able to move the price its own P&L is measured against, which is exactly the assumption the Avellaneda-Stoikov model requires. Flipping it re-runs the identical sim anchored to a synthetic, exogenous GARCH(1,1)/Student-t GBM path (fat tails, volatility clustering) instead of `simulate_random_flow`'s self-referential walk, and surfaces the `|book mid - GBM anchor|` deviation directly in the dashboard, so the self-influence a market maker's own quotes can have on its own scoring is something you can see and measure interactively, not just read about in this README. (`analysis/historical_backtest.py`'s real-BTCUSDT anchor is the equivalent check against genuine market data rather than synthetic GBM — the dashboard doesn't expose that option, since a single fixed 1000-minute series doesn't support reseeding across arbitrary seeds the way a freshly-generated GBM path does.)



## Steamlit Explanation


`streamlit_app.py` wraps the simulation code in a two-tab UI.

**Single run** — choose a market maker (`MarketMaker` or `AvellanedaStoikovMarketMaker`) and its parameters, optionallly add imbalance trader or informed stress and simulate a seed, yielding `Metrics`, `DepthHistory`, `PnLHistory` charts. A **Use GBM exogenous price path** checkbox in the sidebar switches the run from `simulate_random_flow`'s self-referential walk to a GARCH-GBM path anchored via `simulate_historical_flow` (see "Strategy comparison" below). With it on, the tab also plots the GBM anchor against the book's own mid and reports the mean `|book mid - GBM anchor|` deviation, the same self-influence check `analysis/historical_backtest.py` runs against real data. There is also a **Use best known parameters** button which sets parameters to the best ones found in the GARCH-GBM-anchored market maker sweeps for both models, *'the best'* here is only measured against the *imbalance trader not informed*.

`spread=8, max_inventory=50` for `MarketMaker` from `analysis/tune_market_maker.py`

`gamma=0.001, k=0.5` for `AvellanedaStoikovMarketMaker` from `analysis/tune_avellaneda_stoikov.py`

**Compare configurations** — set up two independent market-maker configs (A and B, any mix of model/parameters) and run them against identical input order flow, same reseed-then-diverge pattern `analysis/compare_strategies.py` uses, optionally sharing the same GBM anchor between both sides too. At 1 seed it shows a full P&L breakdown plus a total-P&L-over-time chart for each side; above 1 seed it reseeds and reruns both configs across that many seeds instead and reports the mark-to-market P&L distribution (mean/stdev/min/max/win rate, head-to-head win count, histogram), the same sweep `compare_strategies.py` runs from the command line.


