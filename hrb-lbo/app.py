#!/usr/bin/env python3
"""
LBO Model — Interactive Streamlit Dashboard
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from src.io import load_adjustments, load_assumptions, load_financials
from src.normalize import apply_adjustments, compute_reported_ebitda, get_ltm_or_last_year
from src.operating_model import project_operations
from src.debt import init_debt, run_debt_schedule_fixed
from src.statements import build_bs, build_cf, build_is
from src.returns import compute_exit
from src.sensitivity import run_sensitivity
from src.utils import fmt_mm, fmt_pct, fmt_x

st.set_page_config(
    page_title="LBO Model — H&R Block",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Custom CSS: light modern aesthetic (distinct from PE dashboard) ----
st.markdown("""
<style>
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; }
    h1 { font-weight: 600 !important; letter-spacing: -0.02em; color: #0f172a !important; margin-bottom: 0.25rem !important; }
    h2, h3 { font-weight: 500 !important; color: #334155 !important; font-size: 1rem !important; 
              text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2rem !important; margin-bottom: 0.75rem !important; }
    [data-testid="stMetric"] {
        background: white; padding: 1.25rem 1rem; border-radius: 12px; border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04); transition: box-shadow 0.2s, border-color 0.2s;
    }
    [data-testid="stMetric"]:hover { border-color: #cbd5e1; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; font-weight: 600 !important; color: #0891b2 !important; }
    [data-testid="stMetricLabel"] { font-size: 0.7rem !important; font-weight: 500 !important; color: #64748b !important; 
                                    text-transform: uppercase; letter-spacing: 0.05em; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%) !important; }
    [data-testid="stSidebar"] section { border-bottom: 1px solid #e2e8f0; padding-bottom: 1rem; margin-bottom: 0.5rem; }
    hr { border-color: #e2e8f0 !important; margin: 1.5rem 0 !important; }
    .stAlert { border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)

PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "responsive": True,
}

# Plotly light theme: teal accent, clean backgrounds
PLOTLY_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"family": "sans-serif", "size": 12, "color": "#334155"},
    "title_font": {"size": 14, "color": "#0f172a"},
    "margin": {"t": 50, "b": 50, "l": 50, "r": 30},
    "xaxis": {"gridcolor": "#f1f5f9", "linecolor": "#e2e8f0", "tickfont": {"color": "#64748b"}},
    "yaxis": {"gridcolor": "#f1f5f9", "linecolor": "#e2e8f0", "tickfont": {"color": "#64748b"}},
    "legend": {"bgcolor": "rgba(255,255,255,0.9)", "bordercolor": "#e2e8f0", "borderwidth": 1},
}
CHART_COLORS = ["#0891b2", "#0e7490", "#06b6d4", "#22d3ee", "#67e8f9"]  # teal palette

DATA_DIR = Path(__file__).parent / "data"


def _money_mm(x: float) -> float:
    if x is None or pd.isna(x):
        return float("nan")
    x = float(x)
    return x / 1e6 if abs(x) >= 1e5 else x


@st.cache_data
def load_base_model():
    """Load financials and compute base inputs once."""
    financials = load_financials(DATA_DIR)
    base_assumptions = load_assumptions(DATA_DIR / "assumptions.yaml")
    adjustments = load_adjustments(DATA_DIR / "mapping.yaml")

    is_df = financials["is"]
    reported_ebitda = compute_reported_ebitda(is_df)
    normalized_ebitda = apply_adjustments(
        reported_ebitda, adjustments, is_df["year"]
    )
    ebitda_ltm = get_ltm_or_last_year(normalized_ebitda)
    base_year = int(is_df["year"].max())
    base_revenue = float(is_df.loc[is_df["year"] == base_year, "revenue"].iloc[0])

    return {
        "ebitda_ltm": ebitda_ltm,
        "base_revenue": base_revenue,
        "base_year": base_year,
        "base_assumptions": base_assumptions,
    }


def run_lbo(assumptions: dict, ebitda_ltm: float, base_revenue: float, base_year: int):
    """Run full LBO and return all outputs."""
    tx = assumptions["transaction"]
    entry_mult = float(tx["entry_multiple"])
    entry_ev = entry_mult * ebitda_ltm
    fees = float(tx["fees_pct_ev"]) * entry_ev
    total_uses = entry_ev + fees
    entry_debt = float(tx["debt_pct_ev"]) * total_uses
    entry_equity = total_uses - entry_debt
    min_cash = float(tx["min_cash"])

    ops_df = project_operations(base_revenue, base_year, assumptions)
    init = init_debt(entry_debt, assumptions)
    debt_df = run_debt_schedule_fixed(
        ops_df,
        assumptions["debt"],
        min_cash,
        init["tlb_bop"],
        init["rev_bop"],
    )

    tax_rate = float(assumptions["model"]["tax_rate"])
    is_proj = build_is(ops_df, debt_df, tax_rate)
    bs_proj = build_bs(debt_df, is_proj, entry_equity)
    cf_proj = build_cf(ops_df, debt_df, is_proj)
    exit_result = compute_exit(ops_df, debt_df, assumptions, entry_equity)

    return {
        "entry_ev": entry_ev,
        "entry_debt": entry_debt,
        "entry_equity": entry_equity,
        "ebitda_ltm": ebitda_ltm,
        "ops_df": ops_df,
        "debt_df": debt_df,
        "is_proj": is_proj,
        "bs_proj": bs_proj,
        "cf_proj": cf_proj,
        "exit_result": exit_result,
    }


# ---- Sidebar: Assumptions ----
base = load_base_model()
base_assump = base["base_assumptions"]

st.sidebar.markdown("### Transaction Assumptions")
entry_mult = st.sidebar.slider(
    "Entry Multiple (x EBITDA)",
    min_value=5.0,
    max_value=15.0,
    value=float(base_assump["transaction"]["entry_multiple"]),
    step=0.5,
    help="EV / LTM EBITDA",
    key="entry_mult",
)
exit_mult = st.sidebar.slider(
    "Exit Multiple (x EBITDA)",
    min_value=6.0,
    max_value=14.0,
    value=float(base_assump["transaction"]["exit_multiple"]),
    step=0.5,
    key="exit_mult",
)
debt_pct = st.sidebar.slider(
    "Debt / EV (as decimal, e.g. 0.6 = 60%)",
    min_value=0.30,
    max_value=0.80,
    value=float(base_assump["transaction"]["debt_pct_ev"]),
    step=0.05,
    format="%.2f",
    key="debt_pct",
)
min_cash_mm = st.sidebar.number_input(
    "Min Cash (USD mm)",
    min_value=0,
    max_value=500,
    value=int(base_assump["transaction"]["min_cash"] / 1e6),
    key="min_cash",
)

st.sidebar.markdown("### Operating Assumptions")
revenue_cagr = st.sidebar.slider(
    "Revenue CAGR (e.g. 0.03 = 3%)",
    min_value=0.0,
    max_value=0.15,
    value=float(base_assump["operating"]["revenue_cagr"]),
    step=0.01,
    format="%.2f",
    key="revenue_cagr",
)
ebitda_margin = st.sidebar.slider(
    "EBITDA Margin (e.g. 0.26 = 26%)",
    min_value=0.10,
    max_value=0.45,
    value=float(base_assump["operating"]["ebitda_margin"]),
    step=0.01,
    format="%.2f",
    key="ebitda_margin",
)
tax_rate = st.sidebar.slider(
    "Tax Rate (e.g. 0.24 = 24%)",
    min_value=0.15,
    max_value=0.35,
    value=float(base_assump["model"]["tax_rate"]),
    step=0.01,
    format="%.2f",
    key="tax_rate",
)

# Build assumptions dict
assumptions = {
    "model": {
        **base_assump["model"],
        "tax_rate": tax_rate,
    },
    "operating": {
        **base_assump["operating"],
        "revenue_cagr": revenue_cagr,
        "ebitda_margin": ebitda_margin,
    },
    "transaction": {
        **base_assump["transaction"],
        "entry_multiple": entry_mult,
        "exit_multiple": exit_mult,
        "debt_pct_ev": debt_pct,
        "min_cash": min_cash_mm * 1e6,
    },
    "debt": base_assump["debt"],
}

# ---- Run model ----
result = run_lbo(
    assumptions,
    base["ebitda_ltm"],
    base["base_revenue"],
    base["base_year"],
)
exit_res = result["exit_result"]

# ---- Header ----
st.markdown(
    '<p style="font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0;">Leveraged Buyout Model</p>',
    unsafe_allow_html=True,
)
st.title("H&R Block Case")
st.caption(f"LTM EBITDA: {fmt_mm(result['ebitda_ltm'])} · Base Revenue: {fmt_mm(base['base_revenue'])}")

# ---- KPI Metrics ----
st.subheader("Returns Summary")
r1 = st.columns(6)
with r1[0]:
    st.metric("IRR", fmt_pct(exit_res["irr"]), help="5-year hold IRR")
with r1[1]:
    st.metric("MOIC", fmt_x(exit_res["moic"]), help="Exit equity / Entry equity")
with r1[2]:
    st.metric("Entry Equity", fmt_mm(result["entry_equity"]), help="Sponsor equity at close")
with r1[3]:
    st.metric("Exit Equity", fmt_mm(exit_res["exit_equity"]), help="Equity value at exit")
with r1[4]:
    st.metric("Entry EV", fmt_mm(result["entry_ev"]), help=f"@{entry_mult}x LTM EBITDA")
with r1[5]:
    st.metric("Exit EV", fmt_mm(exit_res["exit_ev"]), help=f"@{exit_mult}x Y5 EBITDA")

r2 = st.columns(4)
with r2[0]:
    st.metric("Entry Debt", fmt_mm(result["entry_debt"]), help="Total debt at close")
with r2[1]:
    st.metric("Net Debt (Y5)", fmt_mm(exit_res["net_debt"]), help="Debt - cash at exit")
with r2[2]:
    st.metric("Y5 EBITDA", fmt_mm(exit_res["ebitda_y5"]), help="Year 5 EBITDA")
with r2[3]:
    st.metric("Y5 Cash", fmt_mm(exit_res["cash"]), help="Cash at exit")

st.divider()

# ---- Page navigation ----
st.sidebar.markdown("---")
st.sidebar.markdown("**Navigation**")
PAGES = ["Overview", "Operating Model", "Debt Schedule", "3 Statements", "Sensitivity"]
page = st.sidebar.radio("Page", PAGES, index=0, key="page_nav")

# ---- Overview ----
if page == "Overview":
    st.subheader("Operating & Debt Trends")

    c1, c2 = st.columns(2)
    with c1:
        ops = result["ops_df"]
        fig = go.Figure()
        years = ops["year"].astype(int).tolist()
        fig.add_trace(
            go.Scatter(x=years, y=ops["revenue"] / 1e6, name="Revenue", mode="lines+markers",
                       line=dict(color=CHART_COLORS[0], width=2.5), marker=dict(size=8))
        )
        fig.add_trace(
            go.Scatter(x=years, y=ops["ebitda"] / 1e6, name="EBITDA", mode="lines+markers",
                       line=dict(color=CHART_COLORS[1], width=2.5), marker=dict(size=8))
        )
        fig.add_trace(
            go.Scatter(x=years, y=ops["fcf"] / 1e6, name="FCF", mode="lines+markers",
                       line=dict(color=CHART_COLORS[2], width=2.5), marker=dict(size=8))
        )
        fig.update_layout(title="Revenue, EBITDA & FCF (USD mm)", height=400, **PLOTLY_LAYOUT)
        fig.update_xaxes(dtick=1, tickformat="d")
        fig.update_yaxes(title_text="USD mm")
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    with c2:
        debt = result["debt_df"]
        fig2 = go.Figure()
        debt_years = debt["year"].astype(int).tolist()
        fig2.add_trace(
            go.Scatter(x=debt_years, y=debt["tlb_eop"] / 1e6, name="TLB", mode="lines+markers",
                       line=dict(color=CHART_COLORS[0], width=2.5), marker=dict(size=8))
        )
        fig2.add_trace(
            go.Scatter(x=debt_years, y=debt["rev_eop"] / 1e6, name="Revolver", mode="lines+markers",
                       line=dict(color=CHART_COLORS[1], width=2.5), marker=dict(size=8))
        )
        fig2.add_trace(
            go.Scatter(x=debt_years, y=debt["cash_eop"] / 1e6, name="Cash", mode="lines+markers",
                       line=dict(color=CHART_COLORS[2], width=2.5), marker=dict(size=8))
        )
        fig2.update_layout(title="Debt & Cash (USD mm)", height=400, **PLOTLY_LAYOUT)
        fig2.update_xaxes(dtick=1, tickformat="d")
        fig2.update_yaxes(title_text="USD mm")
        st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)

    st.subheader("Quick Summary")
    with st.container(border=True):
        st.markdown(
            f"**Entry:** {fmt_mm(result['entry_ev'])} EV @ {entry_mult}x | "
            f"Debt {fmt_mm(result['entry_debt'])} | Equity {fmt_mm(result['entry_equity'])}  \n\n"
            f"**Exit:** {fmt_mm(exit_res['exit_ev'])} EV @ {exit_mult}x | "
            f"Exit equity {fmt_mm(exit_res['exit_equity'])}  \n\n"
            f"**Returns:** IRR {fmt_pct(exit_res['irr'])} | MOIC {fmt_x(exit_res['moic'])}"
        )

# ---- Operating Model ----
elif page == "Operating Model":
    st.subheader("Operating Projections")
    ops = result["ops_df"].copy()
    ops["revenue_mm"] = (ops["revenue"] / 1e6).round(1)
    ops["ebitda_mm"] = (ops["ebitda"] / 1e6).round(1)
    ops["da_mm"] = (ops["da"] / 1e6).round(1)
    ops["ebit_mm"] = (ops["ebit"] / 1e6).round(1)
    ops["capex_mm"] = (ops["capex"] / 1e6).round(1)
    ops["d_nwc_mm"] = (ops["d_nwc"] / 1e6).round(1)
    ops["fcf_mm"] = (ops["fcf"] / 1e6).round(1)
    st.dataframe(
        ops[["year", "revenue_mm", "ebitda_mm", "da_mm", "ebit_mm", "capex_mm", "d_nwc_mm", "fcf_mm"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "year": st.column_config.NumberColumn("Year", format="%d"),
            "revenue_mm": st.column_config.NumberColumn("Revenue", format="%.1f"),
            "ebitda_mm": st.column_config.NumberColumn("EBITDA", format="%.1f"),
            "da_mm": st.column_config.NumberColumn("D&A", format="%.1f"),
            "ebit_mm": st.column_config.NumberColumn("EBIT", format="%.1f"),
            "capex_mm": st.column_config.NumberColumn("CapEx", format="%.1f"),
            "d_nwc_mm": st.column_config.NumberColumn("Δ NWC", format="%.1f"),
            "fcf_mm": st.column_config.NumberColumn("FCF", format="%.1f"),
        },
    )
    fig = go.Figure()
    fig.add_trace(go.Bar(x=ops["year"], y=ops["revenue_mm"], name="Revenue", marker_color=CHART_COLORS[0]))
    fig.add_trace(go.Bar(x=ops["year"], y=ops["ebitda_mm"], name="EBITDA", marker_color=CHART_COLORS[1]))
    fig.update_layout(barmode="group", title="Revenue & EBITDA by Year (USD mm)", **PLOTLY_LAYOUT)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

# ---- Debt Schedule ----
elif page == "Debt Schedule":
    st.subheader("Debt Schedule & Cash Waterfall")
    debt = result["debt_df"].copy()
    debt["tlb_mm"] = (debt["tlb_eop"] / 1e6).round(1)
    debt["rev_mm"] = (debt["rev_eop"] / 1e6).round(1)
    debt["cash_mm"] = (debt["cash_eop"] / 1e6).round(1)
    debt["interest_mm"] = (debt["interest"] / 1e6).round(1)
    debt["fcf_mm"] = (debt["fcf"] / 1e6).round(1)
    debt["mand_amort_mm"] = (debt["mandatory_amort"] / 1e6).round(1)
    debt["opt_paydown_mm"] = (debt["optional_paydown"] / 1e6).round(1)
    debt["rev_draw_mm"] = (debt["revolver_draw"] / 1e6).round(1)
    debt["rev_repay_mm"] = (debt["revolver_repay"] / 1e6).round(1)
    st.dataframe(
        debt[["year", "fcf_mm", "interest_mm", "mand_amort_mm", "opt_paydown_mm", "rev_draw_mm", "rev_repay_mm", "tlb_mm", "rev_mm", "cash_mm"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "year": st.column_config.NumberColumn("Year", format="%d"),
            "fcf_mm": st.column_config.NumberColumn("FCF (mm)", format="%.1f"),
            "interest_mm": st.column_config.NumberColumn("Interest (mm)", format="%.1f"),
            "mand_amort_mm": st.column_config.NumberColumn("Mandatory Amort (mm)", format="%.1f"),
            "opt_paydown_mm": st.column_config.NumberColumn("Optional Paydown (mm)", format="%.1f"),
            "rev_draw_mm": st.column_config.NumberColumn("Revolver Draw (mm)", format="%.1f"),
            "rev_repay_mm": st.column_config.NumberColumn("Revolver Repay (mm)", format="%.1f"),
            "tlb_mm": st.column_config.NumberColumn("TLB EOP (mm)", format="%.1f"),
            "rev_mm": st.column_config.NumberColumn("Revolver EOP (mm)", format="%.1f"),
            "cash_mm": st.column_config.NumberColumn("Cash EOP (mm)", format="%.1f"),
        },
    )

# ---- 3 Statements ----
elif page == "3 Statements":
    st.subheader("Projected Income Statement")
    is_df = result["is_proj"].copy()
    is_df["revenue_mm"] = (is_df["revenue"] / 1e6).round(1)
    is_df["ebitda_mm"] = (is_df["ebitda"] / 1e6).round(1)
    is_cols = ["year", "revenue_mm", "ebitda_mm", "da", "ebit", "interest_expense", "pretax_income", "tax_expense", "net_income"]
    st.dataframe(
        is_df[[c for c in is_cols if c in is_df.columns]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "year": st.column_config.NumberColumn("Year", format="%d"),
            "revenue_mm": st.column_config.NumberColumn("Revenue", format="%.1f"),
            "ebitda_mm": st.column_config.NumberColumn("EBITDA", format="%.1f"),
            "da": st.column_config.NumberColumn("D&A", format="%.0f"),
            "ebit": st.column_config.NumberColumn("EBIT", format="%.0f"),
            "interest_expense": st.column_config.NumberColumn("Interest", format="%.0f"),
            "pretax_income": st.column_config.NumberColumn("Pretax", format="%.0f"),
            "tax_expense": st.column_config.NumberColumn("Tax", format="%.0f"),
            "net_income": st.column_config.NumberColumn("Net Income", format="%.0f"),
        },
    )

    st.subheader("Projected Balance Sheet")
    bs_df = result["bs_proj"].copy()
    bs_df["cash_mm"] = (bs_df["cash"] / 1e6).round(1)
    bs_df["debt_lt_mm"] = (bs_df["debt_lt"] / 1e6).round(1)
    bs_df["debt_st_mm"] = (bs_df["debt_st"] / 1e6).round(1)
    bs_df["equity_mm"] = (bs_df["shareholders_equity"] / 1e6).round(1)
    st.dataframe(
        bs_df[["year", "cash_mm", "debt_lt_mm", "debt_st_mm", "equity_mm"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "year": st.column_config.NumberColumn("Year", format="%d"),
            "cash_mm": st.column_config.NumberColumn("Cash", format="%.1f"),
            "debt_lt_mm": st.column_config.NumberColumn("Debt LT", format="%.1f"),
            "debt_st_mm": st.column_config.NumberColumn("Debt ST", format="%.1f"),
            "equity_mm": st.column_config.NumberColumn("Equity", format="%.1f"),
        },
    )

    st.subheader("Projected Cash Flow")
    cf_df = result["cf_proj"].copy()
    for col in ["cfo", "capex", "cff", "cfi", "fcf"]:
        if col in cf_df.columns:
            cf_df[f"{col}_mm"] = (cf_df[col] / 1e6).round(1)
    cf_cols = [c for c in ["year", "cfo_mm", "capex_mm", "cff_mm", "cfi_mm", "fcf_mm"] if c in cf_df.columns]
    st.dataframe(
        cf_df[cf_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "year": st.column_config.NumberColumn("Year", format="%d"),
            "cfo_mm": st.column_config.NumberColumn("CFO", format="%.1f"),
            "capex_mm": st.column_config.NumberColumn("CapEx", format="%.1f"),
            "cff_mm": st.column_config.NumberColumn("CFF", format="%.1f"),
            "cfi_mm": st.column_config.NumberColumn("CFI", format="%.1f"),
            "fcf_mm": st.column_config.NumberColumn("FCF", format="%.1f"),
        },
    )

# ---- Sensitivity ----
elif page == "Sensitivity":
    st.subheader("IRR / MOIC Sensitivity (Entry × Exit Multiple)")

    entry_grid = [6.0, 7.0, 8.0, 9.0, 10.0]
    exit_grid = [7.0, 8.0, 9.0, 10.0, 11.0]
    base_inputs = {
        "normalized_ebitda_ltm": base["ebitda_ltm"],
        "base_revenue": base["base_revenue"],
        "base_year": base["base_year"],
        "assumptions": assumptions,
    }
    irr_df, moic_df = run_sensitivity(base_inputs, entry_grid, exit_grid)

    c1, c2 = st.columns(2)
    with c1:
        fig_irr = px.imshow(
            irr_df.values * 100,
            x=entry_grid,
            y=exit_grid,
            labels=dict(x="Entry Multiple", y="Exit Multiple", color="IRR %"),
            color_continuous_scale=["#0e7490", "#22c55e", "#facc15"],
            aspect="auto",
        )
        fig_irr.update_layout(title="IRR (%)", **PLOTLY_LAYOUT)
        st.plotly_chart(fig_irr, use_container_width=True, config=PLOTLY_CONFIG)

    with c2:
        fig_moic = px.imshow(
            moic_df.values,
            x=entry_grid,
            y=exit_grid,
            labels=dict(x="Entry Multiple", y="Exit Multiple", color="MOIC"),
            color_continuous_scale=["#f0fdfa", "#0891b2", "#0e7490"],
            aspect="auto",
        )
        fig_moic.update_layout(title="MOIC (x)", **PLOTLY_LAYOUT)
        st.plotly_chart(fig_moic, use_container_width=True, config=PLOTLY_CONFIG)

    with st.expander("IRR Table", expanded=False):
        st.dataframe(irr_df.style.format("{:.1%}"), use_container_width=True)
    with st.expander("MOIC Table", expanded=False):
        st.dataframe(moic_df.style.format("{:.2f}x"), use_container_width=True)
