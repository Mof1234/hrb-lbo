"""EBITDA normalization for one-off adjustments."""

from __future__ import annotations

import pandas as pd


def compute_reported_ebitda(is_df: pd.DataFrame) -> pd.Series:
    """Compute reported EBITDA from income statement."""
    rev = pd.to_numeric(is_df["revenue"], errors="coerce")
    if "ebitda" in is_df.columns:
        return pd.to_numeric(is_df["ebitda"], errors="coerce")
    # EBITDA = revenue - cogs - opex (or EBIT + D&A)
    if "cogs" in is_df.columns and "opex" in is_df.columns:
        cogs = pd.to_numeric(is_df["cogs"], errors="coerce").fillna(0)
        opex = pd.to_numeric(is_df["opex"], errors="coerce").fillna(0)
        return rev - cogs - opex
    # EBIT + D&A
    if "da" in is_df.columns:
        da = pd.to_numeric(is_df["da"], errors="coerce").fillna(0)
        ebit = (
            pd.to_numeric(is_df.get("pretax_income", 0), errors="coerce").fillna(0)
            + pd.to_numeric(is_df.get("interest_expense", 0), errors="coerce").fillna(0)
        )
        return ebit + da
    return pd.Series(dtype=float)


def apply_adjustments(
    ebitda_series: pd.Series,
    adj_dict: dict,
    year_series: pd.Series | None = None,
) -> pd.Series:
    """
    Apply addbacks (positive in adj_dict add to EBITDA).
    adj_dict: {year: {adjustment_name: amount}} where amount > 0 is addback.
    If year_series provided, map by position; else assume ebitda_series.index is year.
    """
    out = ebitda_series.copy()
    year_idx = year_series if year_series is not None else pd.Series(out.index)
    for i, year in enumerate(year_idx):
        y = int(year) if hasattr(year, "item") else int(year)
        if str(y) in adj_dict:
            adj = adj_dict[str(y)]
            total_adj = sum(float(v) for v in adj.values() if v)
            out.iloc[i] = out.iloc[i] + total_adj
    return out


def get_ltm_or_last_year(normalized_ebitda: pd.Series) -> float:
    """Get LTM or last FY normalized EBITDA."""
    if normalized_ebitda.empty:
        return 0.0
    return float(normalized_ebitda.iloc[-1])
