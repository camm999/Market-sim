# Market Sim

![Tests](https://github.com/camm999/Market-sim/actions/workflows/tests.yml/badge.svg)

A limit order book (LOB) simulator written from scratch in Python — the matching engine, random order flow, a simple market-making agent, and metrics tracking, with a small pytest suite covering the core engine.

## Features

- **Matching engine** (`lob/book.py`) — limit and market orders, price-time priority, partial fills, cancellation.
- **Random order flow** (`simulator/random_flow.py`) — Poisson-style arrivals of random limit/market orders around the mid price, to simulate a live market.
- **Market maker** (`simulator/market_maker.py`) — a simple agent that continuously quotes a bid and ask around mid, tracks its own inventory/cash, and skews its quotes against inventory to manage risk.
- **Metrics** (`metrics/metrics.py`) — tracks mid price, spread, depth, and order book imbalance over a run, and plots them.
- **Tests** (`tests/test_book.py`) — pytest unit tests covering matching, price-time priority, partial fills, market order sweeps, and cancellation.

## Project structure

```
market_sim/
├── lob/
│   └── book.py           # core order book: Order, LimitOrderBook
├── simulator/
│   ├── random_flow.py    # random order flow generator
│   └── market_maker.py   # market-making agent
├── metrics/
│   └── metrics.py        # metrics tracking + plotting
├── tests/
│   └── test_book.py      # pytest unit tests
├── main.py                # demo entry point
├── requirements.txt
└── diary.md               # dev log
```

## Quickstart

```bash
git clone <your-repo-url>
cd market_sim
pip install -r requirements.txt
python main.py
```

`main.py` runs a short manual demo — placing, matching, and cancelling orders — then a 500-step random-flow simulation with the market maker active, and saves a chart of mid price / spread / imbalance to `simulation.png`.

## Running tests

```bash
python -m pytest -v
```

## How the order book works

A limit order book (LOB) is the mechanism an electronic exchange uses to match buyers and sellers in real time. Every time a trader submits an order, the exchange doesn't magically "find a counterparty" — instead it places that order into the book, a structured list of all outstanding buy and sell interest.

Buy orders (bids) are sorted so the highest bid represents the most someone is willing to pay, and sell orders (asks) are sorted so the lowest ask represents the cheapest someone is willing to sell. These two prices form the top of the book, and the difference between them is the **bid-ask spread**, a key measure of market liquidity.

When a new order arrives, the exchange checks whether its price is good enough to trade immediately against the opposite side — this is called being **marketable**. A buy order priced above the best ask will instantly execute against the cheapest available sell orders. Trades always follow **price-time priority**: better prices match first, and among equal prices, older orders match before newer ones. If the incoming order isn't fully filled, whatever remains is added to the book at its limit price.

`LimitOrderBook` stores bids and asks in dictionaries mapping price → FIFO queue, which enforces price-time priority. `_best_bid()`/`_best_ask()` identify the top of the book. When an order arrives through `add_limit_order()`, the book checks whether it's marketable and matches it inside `_match_buy()`/`_match_sell()`, reducing sizes on both sides and recording each trade. Fully filled resting orders are removed from their queues, and empty price levels are deleted. Any unfilled remainder is added to the book. `snapshot()` returns a summary of the current state — best bid/ask, depth at each price, and recent trades.

## How the market maker works

A market maker doesn't bet on direction — it continuously posts both a bid and an ask around the current price, earning the spread on round trips. In exchange for supplying that liquidity, it absorbs inventory risk: every fill pushes its position long or short, so `MarketMaker` skews its quotes against its own inventory (long → quote lower, short → quote higher) to lean back toward flat instead of letting risk build up unbounded, and stops adding to a side once a configurable `max_inventory` limit is hit.

## Example output

Running `main.py` produces `simulation.png` — mid price, spread, and order book imbalance over the course of the simulated run.
