# streamlit_app.py
"""Interactive dashboard for market_sim.

wraps the existing simulate_random_flow / MarketMaker / AvellanedaStoikovMarketMaker
code in a UI so simulation parameters (spread, max_inventory, gamma/k, ...) can be
tweaked and re-run live instead of only via `python main.py`'s static PNG output.

Run with:
    streamlit run streamlit_app.py
"""

import contextlib
import io
import random
import statistics
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import streamlit as st

from analysis.stress_test_market_maker import GARCH_OMEGA
from lob.book import LimitOrderBook, Side
from metrics.depth_history import DepthHistory
from metrics.metrics import Metrics
from metrics.pnl_history import PnLHistory
from simulator.avellaneda_stoikov import AvellanedaStoikovMarketMaker
from simulator.gbm_flow import generate_garch_gbm_path, generate_scheduled_drift_garch_gbm_path
from simulator.historical_flow import simulate_historical_flow
from simulator.imbalance_trader import ImbalanceTrader
from simulator.informed_trader import InformedTrader
from simulator.market_maker import MarketMaker
from simulator.random_flow import simulate_random_flow

# Best-scoring grid cells from the multi-seed tuning sweeps (50 seeds each,
# 500 steps), re-run against a GARCH(1,1)/Student-t GBM exogenous price path
# (simulator/gbm_flow.py) rather than simulate_random_flow's self-referential walk 
BEST_LINEAR: Dict[str, float] = {"size": 5, "max_inventory": 50, "spread": 8, "vol_coef": 1.0, "skew_coef": 1.0}
BEST_LINEAR_STATS = "mean P&L ≈ 2405.79, 92% profitable"
BEST_AVELLANEDA: Dict[str, float] = {"size": 5, "max_inventory": 50, "gamma": 0.001, "k": 0.5}
BEST_AVELLANEDA_STATS = "mean P&L ≈ 1438.45, 86% profitable"


def _apply_best_params() -> None:
    """gives session_state with the best-known config for selected model.
    Must run as a button's on_click callback (which fires before
    the widgets below are re-created on the resulting rerun) rather than inline 
    in the script body, or Streamlit would ignore the new values until
    the rerun after this one."""
    best = BEST_LINEAR if st.session_state["mm_type"] == "Linear heuristic (MarketMaker)" else BEST_AVELLANEDA
    for key, value in best.items():
        st.session_state[key] = value


def _informed_schedule(steps: int) -> List[Tuple[int, int, Side]]:
    """The two 50-step drift windows (buy, then sell) used whenever 'Informed trader' is
    checked, a quarter and three-quarters of the way through the run. Shared between
    InformedTrader's own construction and generate_scheduled_drift_garch_gbm_path's anchor below,
    so a GBM-anchored run's price actually drifts during the same window InformedTrader
    trades in, see read me"""
    w1_start, w1_end = steps // 4, steps // 4 + 50
    w2_start, w2_end = 3 * steps // 4, 3 * steps // 4 + 50
    return [(w1_start, w1_end, "buy"), (w2_start, w2_end, "sell")]


def _build_market_maker(cfg: Dict, steps: int) -> MarketMaker:
    if cfg["model"] == "Linear heuristic":
        return MarketMaker(
            spread=cfg["spread"],
            size=cfg["size"],
            max_inventory=cfg["max_inventory"],
            vol_coef=cfg["vol_coef"],
            skew_coef=cfg["skew_coef"],
        )
    return AvellanedaStoikovMarketMaker(
        size=cfg["size"], max_inventory=cfg["max_inventory"], gamma=cfg["gamma"], k=cfg["k"], total_steps=steps
    )


def _run_config(
    cfg: Dict, seed: int, steps: int, use_gbm: bool, prices: Optional[List[float]]
) -> Tuple[MarketMaker, LimitOrderBook, Metrics, PnLHistory]:
    """Run one full sim for one comparison tab config, on its own book,
    identical reseed to other config allows for strategic logic to move book.
    When use_gbm is set, prices also anchor to the GBM path, not just the identical seed."""
    random.seed(seed)
    book = LimitOrderBook()
    mm = _build_market_maker(cfg, steps)
    imbalance_trader = (
        ImbalanceTrader(threshold=cfg["imbalance_threshold"], size=cfg["size"], max_inventory=cfg["max_inventory"])
        if cfg["use_imbalance"]
        else None
    )
    informed_trader = InformedTrader(schedule=_informed_schedule(steps)) if cfg["use_informed"] else None

    metrics = Metrics()
    pnl_history = PnLHistory()
    with contextlib.redirect_stdout(io.StringIO()):  # both flows print per-step progress; silence it here
        if use_gbm:
            assert prices is not None
            simulate_historical_flow(
                book,
                prices,
                market_maker=mm,
                imbalance_trader=imbalance_trader,
                informed_trader=informed_trader,
                metrics=metrics,
                pnl_history=pnl_history,
            )
        else:
            simulate_random_flow(
                book,
                steps=steps,
                sleep=0,
                market_maker=mm,
                imbalance_trader=imbalance_trader,
                informed_trader=informed_trader,
                metrics=metrics,
                pnl_history=pnl_history,
            )
    return mm, book, metrics, pnl_history


def _config_inputs(label: str, key_prefix: str, default_model: str) -> Dict:
    """render one side's (A or B) full config controls and return them as a
    dict"""
    st.markdown(f"**{label}**")
    model = st.radio(
        "Model",
        ["Linear heuristic", "Avellaneda-Stoikov"],
        key=f"{key_prefix}_model",
        index=0 if default_model == "Linear heuristic" else 1,
    )
    size = st.slider("Quote size", min_value=1, max_value=20, value=5, key=f"{key_prefix}_size")
    max_inventory = st.slider(
        "Max inventory", min_value=5, max_value=200, value=50, step=5, key=f"{key_prefix}_max_inv"
    )

    cfg: Dict = {"model": model, "size": size, "max_inventory": max_inventory}
    if model == "Linear heuristic":
        cfg["spread"] = st.slider("Base spread", min_value=0, max_value=20, value=2, key=f"{key_prefix}_spread")
        cfg["vol_coef"] = st.slider(
            "vol_coef", min_value=0.0, max_value=3.0, value=1.0, step=0.1, key=f"{key_prefix}_vol_coef"
        )
        cfg["skew_coef"] = st.slider(
            "skew_coef", min_value=0.0, max_value=3.0, value=1.0, step=0.1, key=f"{key_prefix}_skew_coef"
        )
    else:
        cfg["gamma"] = st.number_input(
            "gamma (risk aversion)",
            min_value=0.00001,
            max_value=0.01,
            value=0.0001,
            step=0.00001,
            format="%.5f",
            key=f"{key_prefix}_gamma",
        )
        cfg["k"] = st.slider(
            "k (order-arrival decay)", min_value=0.1, max_value=5.0, value=1.5, step=0.1, key=f"{key_prefix}_k"
        )

    cfg["use_imbalance"] = st.checkbox("Imbalance trader", value=True, key=f"{key_prefix}_use_imb")
    cfg["imbalance_threshold"] = (
        st.slider(
            "Imbalance threshold", min_value=0.1, max_value=0.9, value=0.4, step=0.05, key=f"{key_prefix}_imb_th"
        )
        if cfg["use_imbalance"]
        else 0.4
    )
    cfg["use_informed"] = st.checkbox(
        "Informed trader (adverse-selection stress test)", value=False, key=f"{key_prefix}_use_inf"
    )
    return cfg


st.set_page_config(page_title="market_sim", layout="wide")
st.title("market_sim: interactive dashboard")
st.caption(
    "A thin UI over the existing simulation code, every control here maps directly "
    "to a constructor argument on `MarketMaker`/`AvellanedaStoikovMarketMaker` or "
    "`simulate_random_flow`/`simulate_historical_flow`. See Streamlit On ReadME."
)

tab_single, tab_compare = st.tabs(["Single run", "Compare configurations"])

with st.sidebar:
    st.header("Simulation")
    use_gbm = st.checkbox(
        "Use GBM exogenous price path",
        value=False,
        help="Anchor order flow to a synthetic GARCH(1,1)/Student-t Geometric Brownian Motion "
        "It prevents market maker from influencing the price path. See README for details",
    )
    steps = st.slider("Steps", min_value=100, max_value=1000, value=500, step=50)
    seed = st.number_input("Random seed", min_value=0, value=42, step=1)

    st.header("Market maker")
    mm_type = st.radio("Model", ["Linear heuristic (MarketMaker)", "Avellaneda-Stoikov"], key="mm_type")

    best_stats = BEST_LINEAR_STATS if mm_type == "Linear heuristic (MarketMaker)" else BEST_AVELLANEDA_STATS
    best_script = "tune_market_maker" if mm_type == "Linear heuristic (MarketMaker)" else "tune_avellaneda_stoikov"
    st.button("Use best known parameters", on_click=_apply_best_params)
    st.caption(
        f"From `analysis/{best_script}.py`'s 50-seed sweep against a **GBM exogenous price path** "
        f"(not `simulate_random_flow`'s self-referential walk — see README's \"Tuning against an "
        f"exogenous price\" section): {best_stats}."
    )

    size = st.slider("Quote size", min_value=1, max_value=20, value=5, key="size")
    max_inventory = st.slider("Max inventory", min_value=5, max_value=200, value=50, step=5, key="max_inventory")

    if mm_type == "Linear heuristic (MarketMaker)":
        spread = st.slider("Base spread", min_value=0, max_value=20, value=2, key="spread")
        vol_coef = st.slider("vol_coef", min_value=0.0, max_value=3.0, value=1.0, step=0.1, key="vol_coef")
        skew_coef = st.slider("skew_coef", min_value=0.0, max_value=3.0, value=1.0, step=0.1, key="skew_coef")
    else:
        gamma = st.number_input(
            "gamma (risk aversion)",
            min_value=0.00001,
            max_value=0.01,
            value=0.0001,
            step=0.00001,
            format="%.5f",
            key="gamma",
        )
        k = st.slider("k (order-arrival decay)", min_value=0.1, max_value=5.0, value=1.5, step=0.1, key="k")

    st.header("Other participants")
    use_imbalance = st.checkbox("Imbalance trader", value=True)
    if use_imbalance:
        imbalance_threshold = st.slider("Imbalance threshold", min_value=0.1, max_value=0.9, value=0.4, step=0.05)

    use_informed = st.checkbox(
        "Informed trader (adverse-selection stress test)",
        value=False,
        help="Fires two scripted directional windows (buy, then sell) partway through the run, "
        "the same scenario analysis/stress_test_market_maker.py uses. Combined with the GBM "
        "toggle above, the price path itself drifts during these same windows (see "
        "simulator/gbm_flow.py's generate_scheduled_drift_garch_gbm_path) so the informed trader still "
        "has a real move to trade ahead of, instead of a drift only simulate_random_flow's "
        "self-referential walk could produce.",
    )

    run = st.button("Run simulation", type="primary")

with tab_single:
    if run:
        random.seed(int(seed))
        book = LimitOrderBook()

        mm: MarketMaker
        if mm_type == "Linear heuristic (MarketMaker)":
            mm = MarketMaker(
                spread=spread,
                size=size,
                max_inventory=max_inventory,
                vol_coef=vol_coef,
                skew_coef=skew_coef,
            )
        else:
            mm = AvellanedaStoikovMarketMaker(
                size=size,
                max_inventory=max_inventory,
                gamma=gamma,
                k=k,
                total_steps=steps,
            )

        imbalance_trader = ImbalanceTrader(threshold=imbalance_threshold, size=size) if use_imbalance else None

        informed_schedule = _informed_schedule(steps) if use_informed else None
        informed_trader = InformedTrader(schedule=informed_schedule) if informed_schedule is not None else None

        depth_history = DepthHistory()
        pnl_history = PnLHistory()

        prices = None
        if use_gbm:
            if informed_schedule is not None:
                prices = generate_scheduled_drift_garch_gbm_path(
                    steps, int(seed), informed_schedule, omega=GARCH_OMEGA
                )
            else:
                prices = generate_garch_gbm_path(steps, int(seed))
            with st.spinner(f"Running {len(prices)} steps against a GBM price path..."):
                metrics = simulate_historical_flow(
                    book,
                    prices,
                    market_maker=mm,
                    imbalance_trader=imbalance_trader,
                    informed_trader=informed_trader,
                    depth_history=depth_history,
                    pnl_history=pnl_history,
                )
        else:
            with st.spinner(f"Running {steps} steps..."):
                metrics = simulate_random_flow(
                    book,
                    steps=steps,
                    sleep=0,
                    market_maker=mm,
                    imbalance_trader=imbalance_trader,
                    informed_trader=informed_trader,
                    depth_history=depth_history,
                    pnl_history=pnl_history,
                )

        st.success("Done.")

        if prices is not None:
            deviations = [abs(m - p) for m, p in zip(metrics.mid_prices, prices) if m is not None]
            mean_deviation = sum(deviations) / len(deviations) if deviations else 0.0
            st.metric("Mean |book mid − GBM anchor|", f"{mean_deviation:.3f}")
            st.caption(
                "How far this market maker's own book mid strayed from the synthetic "
                "GBM price it was quoting against, on average, i.e  0 would mean the"
                " market maker's quotes never moved the book away from the anchor price."
            )

        col1, col2 = st.columns(2)
        with col1:
            st.subheader(mm_type)
            st.metric("Mark-to-market", f"{mm.mark_to_market(book):.2f}")
            st.metric("Spread P&L", f"{mm.spread_pnl:.2f}")
            st.metric("Inventory P&L", f"{mm.inventory_pnl(book):.2f}")
            st.metric("Final inventory", mm.inventory)
        with col2:
            if imbalance_trader is not None:
                st.subheader("Imbalance trader")
                st.metric("Mark-to-market", f"{imbalance_trader.mark_to_market(book):.2f}")
                st.metric("Final inventory", imbalance_trader.inventory)

        st.subheader("Mid price, spread, imbalance")
        st.pyplot(metrics.plot())

        if prices is not None:
            st.subheader("GBM anchor price vs. simulated book mid")
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(prices, label="GBM anchor price", color="tab:blue", linewidth=2)
            ax.plot(metrics.mid_prices, label=f"{mm_type} book mid", color="tab:orange", alpha=0.8)
            ax.set_xlabel("Step")
            ax.set_ylabel("Price")
            ax.legend()
            fig.tight_layout()
            st.pyplot(fig)
            st.caption(
                "Any gap between the two lines is the market maker's own resting quotes "
                "perturbing the book away from the actual exogenous price. This is not noise, since "
                "both are driven by the identical GBM path."
            )

        st.subheader("Market maker P&L: spread capture vs. inventory risk")
        st.pyplot(pnl_history.plot())

        st.subheader("Order book depth over time")
        st.pyplot(depth_history.plot())

        if mm_type == "Avellaneda-Stoikov":
            st.caption(
                "Note: half-spread and reservation price aren't plotted here, "
                "see analysis/avellaneda_stoikov_demo.py for the horizon-decay chart."
            )
    else:
        st.info("Set parameters in the sidebar and click **Run simulation**.")

with tab_compare:
    st.caption(
        "Run two market-maker configurations against identical input order flow (same "
        "seed(s), separate books) and compare their P&L head-to-head, the same "
        "'reseed then diverge' pattern `analysis/compare_strategies.py` uses. Toggle a GBM "
        "exogenous price path below to remove the mid-price self-influence bias from the "
        "comparison too."
    )

    top1, top2, top3 = st.columns(3)
    with top1:
        cmp_use_gbm = st.checkbox("Use GBM exogenous price path", value=False, key="cmp_use_gbm")
    with top2:
        cmp_steps = st.slider("Steps", min_value=100, max_value=1000, value=500, step=50, key="cmp_steps")
    with top3:
        n_seeds = st.slider(
            "Number of seeds",
            min_value=1,
            max_value=200,
            value=1,
            key="cmp_n_seeds",
            help="1 = single run with full P&L breakdown and plots. More than 1 reseeds and "
            "reruns both configs that many times and reports the mark-to-market P&L "
            "distribution instead, like analysis/compare_strategies.py's sweep.",
        )
    base_seed = st.number_input("Base seed", min_value=0, value=0, step=1, key="cmp_base_seed")

    colA, colB = st.columns(2)
    with colA:
        cfg_a = _config_inputs("Configuration A", "cmp_a", "Avellaneda-Stoikov")
    with colB:
        cfg_b = _config_inputs("Configuration B", "cmp_b", "Linear heuristic")

    run_cmp = st.button("Run comparison", type="primary", key="cmp_run")

    if run_cmp:
        pnls_a: List[float] = []
        pnls_b: List[float] = []
        detail_a = detail_b = None
        detail_prices: Optional[List[float]] = None

        # fixed for the whole sweep (doesn't depend on seed since same schedule)
        informed_schedule = (
            _informed_schedule(cmp_steps) if (cfg_a["use_informed"] or cfg_b["use_informed"]) else None
        )

        progress = st.progress(0.0, text=f"Running seed 1/{n_seeds}...")
        for i in range(n_seeds):
            seed_i = int(base_seed) + i
            # A fresh GBM path per seed shared between A and B, rather than one fixed path reused
            # and matches analysis/compare_strategies.py's run_once
        
            if cmp_use_gbm:
                if informed_schedule is not None:
                    prices_i = generate_scheduled_drift_garch_gbm_path(
                        cmp_steps, seed_i, informed_schedule, omega=GARCH_OMEGA
                    )
                else:
                    prices_i = generate_garch_gbm_path(cmp_steps, seed_i)
            else:
                prices_i = None
            result_a = _run_config(cfg_a, seed_i, cmp_steps, cmp_use_gbm, prices_i)
            result_b = _run_config(cfg_b, seed_i, cmp_steps, cmp_use_gbm, prices_i)
            pnls_a.append(result_a[0].mark_to_market(result_a[1]))
            pnls_b.append(result_b[0].mark_to_market(result_b[1]))
            if n_seeds == 1:
                detail_a, detail_b = result_a, result_b
                detail_prices = prices_i
            progress.progress((i + 1) / n_seeds, text=f"Running seed {i + 1}/{n_seeds}...")
        progress.empty()

        st.success(f"Done — {n_seeds} seed{'s' if n_seeds != 1 else ''}.")

        if n_seeds == 1:
            mm_a, book_a, metrics_a, pnl_hist_a = detail_a
            mm_b, book_b, metrics_b, pnl_hist_b = detail_b

            dcol1, dcol2 = st.columns(2)
            for dcol, label, mm_x, book_x, metrics_x in (
                (dcol1, "A", mm_a, book_a, metrics_a),
                (dcol2, "B", mm_b, book_b, metrics_b),
            ):
                with dcol:
                    st.markdown(f"**Configuration {label}**")
                    st.metric("Mark-to-market", f"{mm_x.mark_to_market(book_x):.2f}")
                    st.metric("Spread P&L", f"{mm_x.spread_pnl:.2f}")
                    st.metric("Inventory P&L", f"{mm_x.inventory_pnl(book_x):.2f}")
                    if detail_prices is not None:
                        deviations = [
                            abs(m - p) for m, p in zip(metrics_x.mid_prices, detail_prices) if m is not None
                        ]
                        deviation = sum(deviations) / len(deviations) if deviations else 0.0
                        st.metric("Mean |book mid − GBM anchor|", f"{deviation:.3f}")

            st.subheader("Total P&L over time")
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(pnl_hist_a.total_pnl, label=f"A: {cfg_a['model']}", color="tab:blue")
            ax.plot(pnl_hist_b.total_pnl, label=f"B: {cfg_b['model']}", color="tab:orange")
            ax.axhline(0, color="grey", linewidth=0.8)
            ax.set_xlabel("Step")
            ax.set_ylabel("Total P&L (mark-to-market)")
            ax.legend()
            fig.tight_layout()
            st.pyplot(fig)
        else:

            def _summarize(pnls: List[float]) -> Dict[str, float]:
                wins = sum(1 for p in pnls if p > 0)
                return {
                    "mean": statistics.mean(pnls),
                    "stdev": statistics.stdev(pnls) if len(pnls) > 1 else 0.0,
                    "min": min(pnls),
                    "max": max(pnls),
                    "win_rate": wins / len(pnls),
                }

            summary_a = _summarize(pnls_a)
            summary_b = _summarize(pnls_b)

            scol1, scol2 = st.columns(2)
            for scol, label, cfg_x, summary in (
                (scol1, "A", cfg_a, summary_a),
                (scol2, "B", cfg_b, summary_b),
            ):
                with scol:
                    st.markdown(f"**Configuration {label} — {cfg_x['model']}**")
                    st.metric("Mean P&L", f"{summary['mean']:.2f}")
                    st.metric("Stdev", f"{summary['stdev']:.2f}")
                    st.metric("Min / Max", f"{summary['min']:.2f} / {summary['max']:.2f}")
                    st.metric("Profitable", f"{summary['win_rate'] * 100:.1f}%")

            head_to_head = sum(1 for a, b in zip(pnls_a, pnls_b) if a > b)
            st.caption(
                f"Configuration A beat Configuration B head-to-head in {head_to_head}/{n_seeds} "
                f"runs ({head_to_head / n_seeds * 100:.1f}%)."
            )

            st.subheader("Mark-to-market P&L distribution across seeds")
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.hist(pnls_a, bins=min(30, n_seeds), alpha=0.6, label=f"A: {cfg_a['model']}", color="tab:blue")
            ax.hist(pnls_b, bins=min(30, n_seeds), alpha=0.6, label=f"B: {cfg_b['model']}", color="tab:orange")
            ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
            ax.set_xlabel("Mark-to-market P&L")
            ax.set_ylabel("Number of runs")
            ax.legend()
            fig.tight_layout()
            st.pyplot(fig)
    else:
        st.info("Configure A and B above and click **Run comparison**.")
