"""Build full 3-statement projections from operating model + debt schedule."""

from __future__ import annotations

import pandas as pd


def build_is(ops_df: pd.DataFrame, debt_df: pd.DataFrame, tax_rate: float) -> pd.DataFrame:
    """Income statement: ops + interest from debt schedule."""
    is_df = ops_df[["year", "revenue", "ebitda", "da", "ebit"]].copy()
    is_df = is_df.merge(debt_df[["year", "interest"]], on="year", how="left")
    is_df["interest_expense"] = is_df["interest"].fillna(0)
    is_df["pretax_income"] = is_df["ebit"] - is_df["interest_expense"]
    is_df["tax_expense"] = is_df["pretax_income"].clip(lower=0) * tax_rate
    is_df["net_income"] = is_df["pretax_income"] - is_df["tax_expense"]
    is_df = is_df.drop(columns=["interest"], errors="ignore")
    return is_df


def build_bs(
    debt_df: pd.DataFrame,
    is_df: pd.DataFrame,
    initial_equity: float,
) -> pd.DataFrame:
    """Balance sheet: cash, debt from debt schedule; equity roll-forward."""
    merged = debt_df.merge(is_df[["year", "net_income"]], on="year", how="left")
    rows = []
    equity = initial_equity
    for _, row in merged.iterrows():
        year = int(row["year"])
        equity = equity + float(row["net_income"])
        rows.append({
            "year": year,
            "cash": row["cash_eop"],
            "debt_lt": row["tlb_eop"],
            "debt_st": row["rev_eop"],
            "shareholders_equity": equity,
        })
    return pd.DataFrame(rows)


def build_cf(
    ops_df: pd.DataFrame,
    debt_df: pd.DataFrame,
    is_df: pd.DataFrame,
) -> pd.DataFrame:
    """Cash flow statement: CFO, Capex, CFF, FCF."""
    merged = ops_df.merge(debt_df, on="year", how="left").merge(
        is_df[["year", "net_income"]], on="year", how="left"
    )
    merged["cfo"] = merged["net_income"] + merged["da"]
    merged["capex"] = merged["capex"]
    rd = merged["revolver_draw"].fillna(0)
    ma = merged["mandatory_amort"].fillna(0)
    op = merged["optional_paydown"].fillna(0)
    rr = merged["revolver_repay"].fillna(0)
    merged["cff"] = rd - ma - op - rr
    merged["cfi"] = merged["capex"]
    fcf_col = "fcf_x" if "fcf_x" in merged.columns else "fcf"
    merged["fcf"] = merged[fcf_col]
    return merged[["year", "cfo", "capex", "cff", "cfi", "fcf"]]
