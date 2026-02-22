"""Operating projections: revenue, EBITDA, FCF."""

from __future__ import annotations

import pandas as pd


def project_operations(
    base_revenue: float,
    base_year: int,
    assumptions: dict,
) -> pd.DataFrame:
    """
    Project 5-year operating model.
    Output columns: year, revenue, ebitda, da, ebit, taxes, nopat, capex, d_nwc, fcf
    """
    op = assumptions.get("operating", {})
    model = assumptions.get("model", {})
    cagr = float(op.get("revenue_cagr", 0.03))
    margin = float(op.get("ebitda_margin", 0.26))
    da_pct = float(op.get("da_pct_rev", 0.02))
    capex_pct = float(op.get("capex_pct_rev", 0.015))
    nwc_pct = float(op.get("nwc_pct_rev", 0.01))
    tax_rate = float(model.get("tax_rate", 0.24))
    n_years = int(model.get("projection_years", 5))
    start_year = int(model.get("start_year", base_year + 1))

    rows = []
    prev_rev = base_revenue

    for i in range(n_years):
        year = start_year + i
        revenue = prev_rev * (1 + cagr)
        ebitda = revenue * margin
        da = revenue * da_pct
        ebit = ebitda - da
        taxes = max(0.0, ebit) * tax_rate
        nopat = ebit - taxes
        capex = -abs(revenue * capex_pct)  # outflow
        d_nwc = (revenue - prev_rev) * nwc_pct
        fcf = nopat + da + capex - d_nwc

        rows.append({
            "year": year,
            "revenue": revenue,
            "ebitda": ebitda,
            "da": da,
            "ebit": ebit,
            "taxes": taxes,
            "nopat": nopat,
            "capex": capex,
            "d_nwc": d_nwc,
            "fcf": fcf,
        })
        prev_rev = revenue

    return pd.DataFrame(rows)
