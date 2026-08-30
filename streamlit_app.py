# streamlit_app.py
"""Interactive dashboard for market_sim.

Wraps the existing simulate_random_flow / MarketMaker / AvellanedaStoikovMarketMaker
code in a UI so simulation parameters (spread, max_inventory, gamma/k, ...) can be
tweaked and re-run live instead of only via `python main.py`'s static PNG output.

Run with:
    streamlit run streamlit_app.py
"""

import random
from typing import Dict

import streamlit as st

from lob.book import LimitOrderBook
from metrics.depth_history import DepthHistory
from metrics.pnl_history import PnLHistory
from simulator.avellaneda_stoikov import AvellanedaStoikovMarketMaker
from simulator.imbalance_trader import ImbalanceTrader
from simulator.informed_trader import InformedTrader
from simulator.market_maker import MarketMaker
from simulator.random_flow import simulate_random_flow

# Best-scoring grid cells from the multi-seed tuning sweeps (50 seeds each,
# 500 steps) - see README's "Is that a tuning problem or something
# structural?" / "Does the same apply to Avellaneda-Stoikov?" sections.
# Params the sweep didn't vary are included too (at the value the sweep held
# them fixed at), so clicking the button resets a run to the actual
# best-known config rather than only touching the swept axes.
BEST_LINEAR: Dict[str, float] = {"size": 5, "max_inventory": 10, "spread": 8, "vol_coef": 1.0, "skew_coef": 1.0}
BEST_LINEAR_STATS = "mean P&L ≈ 386.98, 94% profitable"
BEST_AVELLANEDA: Dict[str, float] = {"size": 5, "max_inventory": 50, "gamma": 0.00002, "k": 1.0}
BEST_AVELLANEDA_STATS = "mean P&L ≈ 242.41, 84% profitable"


def _apply_best_params() -> None:
    """Seed the relevant widgets' session_state with the best-known config
    for whichever model is currently selected. Must run as a button's
    on_click callback (which fires before the widgets below are re-created
    on the resulting rerun) rather than inline in the script body, or
    Streamlit would ignore the new values until the rerun after this one."""
    best = BEST_LINEAR if st.session_state["mm_type"] == "Linear heuristic (MarketMaker)" else BEST_AVELLANEDA
    for key, value in best.items():
        st.session_state[key] = value


st.set_page_config(page_title="market_sim", layout="wide")
st.title("market_sim: interactive dashboard")
st.caption(
    "A thin UI over the existing simulation code — every control here maps directly "
    "to a constructor argument on `MarketMaker`/`AvellanedaStoikovMarketMaker` or "
    "`simulate_random_flow`. See the README for what each parameter actually does."
)

with st.sidebar:
    st.header("Simulation")
    steps = st.slider("Steps", min_value=100, max_value=1000, value=500, step=50)
    seed = st.number_input("Random seed", min_value=0, value=42, step=1)

    st.header("Market maker")
    mm_type = st.radio("Model", ["Linear heuristic (MarketMaker)", "Avellaneda-Stoikov"], key="mm_type")

    best_stats = BEST_LINEAR_STATS if mm_type == "Linear heuristic (MarketMaker)" else BEST_AVELLANEDA_STATS
    best_script = "tune_market_maker" if mm_type == "Linear heuristic (MarketMaker)" else "tune_avellaneda_stoikov"
    st.button("Use best known parameters", on_click=_apply_best_params)
    st.caption(f"From `analysis/{best_script}.py`'s 50-seed sweep: {best_stats}.")

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
        "the same scenario analysis/stress_test_market_maker.py uses.",
    )

    run = st.button("Run simulation", type="primary")

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

    informed_trader = None
    if use_informed:
        w1_start, w1_end = steps // 4, steps // 4 + 50
        w2_start, w2_end = 3 * steps // 4, 3 * steps // 4 + 50
        informed_trader = InformedTrader(schedule=[(w1_start, w1_end, "buy"), (w2_start, w2_end, "sell")])

    depth_history = DepthHistory()
    pnl_history = PnLHistory()

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

    st.subheader("Market maker P&L: spread capture vs. inventory risk")
    st.pyplot(pnl_history.plot())

    st.subheader("Order book depth over time")
    st.pyplot(depth_history.plot())

    if mm_type == "Avellaneda-Stoikov":
        st.caption(
            "Note: half-spread and reservation price aren't plotted here — "
            "see analysis/avellaneda_stoikov_demo.py for the horizon-decay chart."
        )
else:
    st.info("Set parameters in the sidebar and click **Run simulation**.")
