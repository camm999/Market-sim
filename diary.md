# Diary

## 2026-08-18

- Limit orders
- Market orders
- FIFO queues (price-time priority)
- Trade records

## 2026-08-19

- Added `simulator/random_flow.py` — works, but need to manage the sleep timing for quicker output.
- Note: run from the project root as `market_sim/...`, not from inside a subfolder.
- Bug: mid price printed as `None` at the start of the simulation — needs a fallback.
- Reminder: mid = (best bid + best ask) / 2 — closest thing to fair value in an LOB. Spread = ask - bid, a direct measure of liquidity/competition.
- To do: metrics (mid/spread/depth/imbalance over time), wire into simulator.

## 2026-08-22

Installed Claude Code to help move this forward. No Python was on the machine at all (just the Windows Store stub) — installed Python 3.12, numpy, and matplotlib.

- Removed a dead duplicate `mid_price()` in `lob/book.py` (a second definition was silently overriding the first).
- Fixed `metrics/metrics.py` — it called `book.get_best_bid()` etc., which never existed on `LimitOrderBook` and would have crashed. Now reads `book.mid_price()` / `book.spread()` / `book.bids` / `book.asks` directly, and tracks trades incrementally (`book.trades[self._trades_seen:]`) instead of double-counting from `snapshot()`'s last-5 window.
- Wired `Metrics` into `simulate_random_flow` — creates one if not passed in, calls `.update(book)` every step, returns it.
- Added a `sleep` param to `simulate_random_flow` (the timing to-do from 08-19) — `main.py` now runs with `sleep=0.01`; the full 500-step sim takes ~5s instead of ~50s.
- Added `Metrics.plot()` — saves mid price / spread / imbalance over the run to `simulation.png`.

- Added Market maker agent.
- Wired it into `simulate_random_flow` as an optional participant each step.
- Updated `main.py` to instantiate a MarketMaker, pass it in, and print its final stats.
- Wrapped `main.py` in a `main()` function guarded by `if __name__ == "__main__":` so it's importable without auto-running the demo.

Goal for this project: get it onto GitHub as a portfolio piece for internship applications. Starting a punch list — tests, README, requirements.txt, git init/push.

- Added `tests/test_book.py` (pytest) — 19 tests covering matching, price-time priority, partial fills, market order sweeps, cancellation, and mid-price/spread edge cases. All passing.
- Rewrote `README.md` — features, project structure, quickstart, testing instructions, and folded in the old LOB/market-maker explanations. Deleted the old plain-text `README` (superseded, and GitHub only renders `README.md`).
- Added `requirements.txt` (numpy, matplotlib, pytest), pinned to installed versions. Verified `pip install -r requirements.txt` + `python -m pytest -v` both work clean from it.
- `git init`, added `.gitignore`, initial commit. Created the GitHub repo (MIT license) at github.com/camm999/Market-sim, merged in the remote's LICENSE (unrelated histories, no conflicts), and pushed. Live: https://github.com/camm999/Market-sim

Punch list for the CV version is done. metrics/init.py & simulator/init.py turned out to already be gone from disk (not needed — Python 3 doesn't require __init__.py).

Wrapping up for today. Reminder: git doesn't auto-sync — after editing anything, need `git add -A`, `git commit -m "..."`, `git push` for it to actually show up on GitHub (Claude can run this cycle on request).

**Next session, in priority order:**
1. GitHub Actions CI — a workflow that runs `pytest` automatically on every push. Cheap to add, and having a green checkmark on the repo reads well to anyone reviewing it.
2. An imbalance-reactive agent — something that actually uses the depth/imbalance data `Metrics` already tracks (e.g. a momentum agent that leans into imbalance, as a contrast to the market maker leaning against its own inventory). Good depth to talk about in an interview.
3. Nice-to-haves if there's time: type hints across `lob/`, `simulator/`, `metrics/`; a `.github/` badge in the README once CI exists.

- Added `.github/workflows/tests.yml` — GitHub Actions runs `pytest` on every push. Added the status badge to `README.md`. First run passed.
- Added `simulator/imbalance_trader.py` — `ImbalanceTrader`, a momentum agent that computes book imbalance itself and hits the market with a buy/sell once it crosses a threshold, betting the imbalance predicts the next move. Contrasts with `MarketMaker`, which trades *against* its own inventory instead of with the book's imbalance. Wired into `simulate_random_flow` as an optional `imbalance_trader` param, and `main.py` now runs one and prints its stats too.
- Added `tests/test_imbalance_trader.py` — 4 tests (balanced book = no trade, buys/sells with imbalance, risk cap stops further trading). 23 tests total, all passing.
- Added `tests/test_market_maker.py` — 7 tests (quoting, replacing stale quotes, fill settlement across steps, inventory skew, risk cap on both sides). Writing the "immediate fill on post" test caught a real correctness issue in `MarketMaker.quote()`: it booked instant fills at its own quoted price instead of the actual traded price. Turns out mathematically unreachable to diverge given how skew is bounded (the quote can only ever reach exactly the opposing best price, never sweep past it) — so it was never producing wrong numbers in practice — but fixed it anyway (`_apply_fills_from_trades`, reads real prices from `book.trades`) since it's the correct approach and more robust if the skew formula ever changes. 30 tests total, all passing.

## 2026-08-23

- Added type hints across `lob/book.py`, `metrics/metrics.py`, `simulator/random_flow.py`, `simulator/market_maker.py`, `simulator/imbalance_trader.py`. Added a `Side = Literal["buy", "sell"]` alias in `lob/book.py` used everywhere a side string is passed around.
- Also declared `LimitOrderBook.last_mid` properly in `__init__` (it was being set dynamically via `hasattr` checks before) and simplified `mid_price()`/`spread()` accordingly.
- Installed `mypy` and actually ran it — caught several real `Optional[float]` narrowing issues in `_match_buy`/`_match_sell`/`_market_buy`/`_market_sell`/`spread()` where `_best_bid()`/`_best_ask()` could theoretically be `None` at the type level even though the surrounding `while`/`if` guards make it impossible at runtime. Fixed with `assert ... is not None` (also a free runtime safety net) rather than suppressing the checker.
- Added `mypy` to `requirements.txt` and a "Type check" step to `.github/workflows/tests.yml`, so it runs automatically on every push alongside pytest.
- 30 tests still passing, mypy clean, `main.py` still runs correctly.

Punch list is now fully done: tests, README, requirements.txt, CI (pytest + mypy), two contrasting trading agents, type hints. Nothing left on the to-do list.

Did an appearance/cleanup pass before starting a new project. Found: `simulator/random_flow.py` used 8-space indentation everywhere (inconsistent with every other file's 4-space), inconsistent operator spacing across `book.py`/`main.py` (`while size>0`, `side= "buy"`, etc.), unused imports (`random`/`time`/`numpy` in `book.py`, `deque`/`numpy` in `random_flow.py`), and `cancel_order`'s not-found path was `return print(...)` (confusing — using print's `None` return as the function's return). Removed the unused imports and fixed `cancel_order`, then ran `black --line-length 100` across the whole codebase to normalize everything else in one pass. 30 tests still pass, mypy still clean, `main.py` still runs correctly. Deliberately did *not* pin black's config or add it to CI — one-time reformat only, by choice.

Speed up the matching engine: `_best_bid()`/`_best_ask()` used to do `max()`/`min()` over every price level's dict key every single call — `O(n)`, and they get called on nearly every operation. Replaced with a heap-based index (`_bid_heap`/`_ask_heap`) alongside each dict: bids store negated prices to simulate a max-heap since `heapq` is min-heap only. Heaps can't cheaply delete from the middle, so used lazy deletion (the pattern `heapq`'s own docs recommend) — stale entries (price level fully matched/cancelled away) get left in place and discarded the next time they'd be the answer, each one only ever popped once, keeping it `O(log n)` amortized. Pushed onto the heap only at the two spots a genuinely new price level gets created (the resting-remainder branches in `_match_buy`/`_match_sell`); deletions need no heap changes at all, that's the whole point of the lazy approach.

Added 3 new tests specifically targeting the lazy-deletion mechanism (out-of-order inserts/removals, levels matched away, a price level emptied then reused later — the case where the heap can end up with a stale + live entry for the same price simultaneously). 33 tests total, all passing, mypy clean.

Added `benchmarks/bench_best_price.py` to actually measure the claim instead of just asserting it: dict `max()` scales linearly with price levels (2.86s at 50k levels), heap peek stays flat (~0.2-0.4ms) regardless of depth — a ~10,000x difference at 50k levels. Updated README with a Performance section showing the numbers, and refreshed the Features/Project structure sections which had gone stale (missing `ImbalanceTrader`, the newer test files, mypy).
