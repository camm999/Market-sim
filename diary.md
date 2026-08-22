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
