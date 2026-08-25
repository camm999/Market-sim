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

Added inline comments explaining the benchmark script step by step (user request, for their own learning).

Added `metrics/depth_history.py` — `DepthHistory` records a full per-price-level depth snapshot every step (not just scalar totals like `Metrics` does), binned as an *offset from mid* rather than absolute price so it stays meaningful as mid drifts over a random-walk run. Bids stored as positive size, asks as negative, so `plot()` can render one heatmap (time x price-offset) with a diverging green/red colormap instead of needing two separate charts. Wired into `simulate_random_flow` as an optional `depth_history` param, `main.py` now saves it to `depth_heatmap.png`. Result actually shows real structure — liquidity bands visibly widening out as the simulation progresses. Added `tests/test_depth_history.py` (4 tests: sign convention, offset-range clipping, same-price-level summing, one frame per update call). 37 tests total, all passing, mypy clean.

Bug: `self._bid_heap` had gone missing from `LimitOrderBook.__init__` (only `_ask_heap` remained) — `AttributeError` on the very first buy order. Restored it. Worth remembering: this would've been caught immediately by `python -m pytest` (most of `test_book.py` exercises `_match_buy`) — running tests before `python main.py` catches these faster.

Tried an animated version of the depth heatmap (GIF, revealing left to right over the run). Got it working but the first attempt produced an 11MB file — way too big to commit. Got it down to ~600KB with lower dpi/fewer frames, then hit a Pillow/Tkinter DLL import error in the test environment (`_imagingtk` blocked by an Application Control policy) while adding a test for it. Decided it wasn't worth the fragility for the payoff — reverted the whole thing back to the last commit. Nothing was ever pushed, so no cleanup needed on GitHub.

Added `analysis/compare_strategies.py` — runs the simulation across 200 independent random seeds (reseeding `random` at the start of each run keeps every seed reproducible regardless of run order) and compares `MarketMaker` vs `ImbalanceTrader` on final mark-to-market P&L, instead of judging either off one anecdotal run. Real result: `ImbalanceTrader` wins on every measure over this random-flow model — mean +378 vs +27, 82% vs 62.5% profitable, and it beats `MarketMaker` head-to-head in 64.5% of seeds. `MarketMaker` also has a much fatter downside tail. Wrote this up honestly in the README rather than just showing the numbers — the result says more about this simplified order flow than about market making in general, since it doesn't capture genuine adverse selection. Added `tests/test_compare_strategies.py` (4 tests: same-seed determinism, different seeds differ, sweep returns one result per seed, summarize doesn't crash). Had to run it via `python -m analysis.compare_strategies` (not `python analysis/compare_strategies.py` directly) for the same sys.path reason as pytest. 41 tests total, all passing, mypy clean across 7 source files (added `analysis` to the CI mypy step too).

Followed up on *why* MarketMaker loses: added `analysis/tune_market_maker.py`, sweeping `spread` x `max_inventory` (6x5 grid, 50 seeds each, ImbalanceTrader held fixed) — 1500 runs, ~22s. Real finding: `max_inventory` dominates. The default (`max_inventory=50`) was too conservative — it stops quoting one side too early in a trending run. Best config (`spread=2, max_inventory=200`) more than triples the baseline mean P&L (90 -> 322 over this sweep's sample), but still doesn't fully close the gap to ImbalanceTrader's ~378 — so the underperformance looks partly tuning, partly structural to this order flow model. Also found a striking non-monotonic "danger zone": mid-range max_inventory (50-100) combined with wide spread (6-8) is *worse* than tight spread at the same cap (down to -227 mean P&L) — hypothesis is that wide spread means bigger skew swings, and a moderate inventory cap gets pinned there often enough for that miscalibration to actually hurt, while a low cap bounds the damage and a high cap rarely gets pinned. Flagged this as a hypothesis in the README, not a verified conclusion - worth digging into further if there's time. mypy caught a real bug while writing this: `set_xticklabels`/`set_yticklabels` need strings, was passing raw ints/floats (worked at runtime since matplotlib silently coerces them, but violated the type contract) - fixed. Added `tests/test_tune_market_maker.py` (3 tests). 44 tests total, all passing, mypy clean across 8 source files.
