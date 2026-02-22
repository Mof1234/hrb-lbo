#!/usr/bin/env python3
"""
Leveraged Buyout Model — H&R Block Case
Base-case 5-year hold: IRR, MOIC, exit equity
3 statements, debt schedules, cash waterfall, sensitivity table
"""

from __future__ import annotations

from pathlib import Path

from src.io import load_adjustments, load_assumptions, load_financials
from src.normalize import apply_adjustments, compute_reported_ebitda, get_ltm_or_last_year
from src.operating_model import project_operations
from src.debt import init_debt, run_debt_schedule_fixed
from src.statements import build_bs, build_cf, build_is
from src.returns import compute_exit
from src.sensitivity import run_sensitivity
from src.utils import fmt_mm, fmt_pct, fmt_x


DATA_DIR = Path(__file__).parent / "data"
OUTPUTS_DIR = Path(__file__).parent / "outputs"


def main() -> None:
    OUTPUTS_DIR.mkdir(exist_ok=True)

    # ---- Step A: Load + normalize ----
    financials = load_financials(DATA_DIR)
    assumptions = load_assumptions(DATA_DIR / "assumptions.yaml")
    adjustments = load_adjustments(DATA_DIR / "mapping.yaml")

    is_df = financials["is"]
    reported_ebitda = compute_reported_ebitda(is_df)
    normalized_ebitda = apply_adjustments(
        reported_ebitda, adjustments, is_df["year"]
    )
    ebitda_ltm = get_ltm_or_last_year(normalized_ebitda)

    base_year = int(is_df["year"].max())
    base_revenue = float(is_df.loc[is_df["year"] == base_year, "revenue"].iloc[0])

    # ---- Step B: Transaction / Sources & Uses ----
    tx = assumptions["transaction"]
    entry_mult = float(tx["entry_multiple"])
    entry_ev = entry_mult * ebitda_ltm
    fees = float(tx["fees_pct_ev"]) * entry_ev
    total_uses = entry_ev + fees
    entry_debt = float(tx["debt_pct_ev"]) * total_uses
    entry_equity = total_uses - entry_debt
    min_cash = float(tx["min_cash"])

    # ---- Step C: Project operations ----
    ops_df = project_operations(base_revenue, base_year, assumptions)

    # ---- Step D: Debt schedule + cash waterfall ----
    init = init_debt(entry_debt, assumptions)
    debt_df = run_debt_schedule_fixed(
        ops_df,
        assumptions["debt"],
        min_cash,
        init["tlb_bop"],
        init["rev_bop"],
    )

    # ---- 3 Statements ----
    tax_rate = float(assumptions["model"]["tax_rate"])
    is_proj = build_is(ops_df, debt_df, tax_rate)
    bs_proj = build_bs(debt_df, is_proj, entry_equity)
    cf_proj = build_cf(ops_df, debt_df, is_proj)

    # ---- Step E: Exit + returns ----
    exit_result = compute_exit(ops_df, debt_df, assumptions, entry_equity)

    # ---- Step F: Sensitivity ----
    entry_grid = [6.0, 7.0, 8.0, 9.0, 10.0]
    exit_grid = [7.0, 8.0, 9.0, 10.0, 11.0]
    base_inputs = {
        "normalized_ebitda_ltm": ebitda_ltm,
        "base_revenue": base_revenue,
        "base_year": base_year,
        "assumptions": assumptions,
    }
    irr_df, moic_df = run_sensitivity(base_inputs, entry_grid, exit_grid)

    # ---- Save outputs ----
    is_proj.to_csv(OUTPUTS_DIR / "projected_is.csv", index=False)
    bs_proj.to_csv(OUTPUTS_DIR / "projected_bs.csv", index=False)
    cf_proj.to_csv(OUTPUTS_DIR / "projected_cf.csv", index=False)
    debt_df.to_csv(OUTPUTS_DIR / "debt_schedule.csv", index=False)

    equity_returns = {
        "initial_equity": entry_equity,
        "exit_equity": exit_result["exit_equity"],
        "irr": exit_result["irr"],
        "moic": exit_result["moic"],
    }
    import pandas as pd
    pd.DataFrame([equity_returns]).to_csv(OUTPUTS_DIR / "equity_returns.csv", index=False)

    irr_df.to_csv(OUTPUTS_DIR / "sensitivity_irr.csv")
    moic_df.to_csv(OUTPUTS_DIR / "sensitivity_moic.csv")

    # ---- Printed summary ----
    print("\n" + "=" * 60)
    print("LBO Base Case (5-Year Hold) — Summary")
    print("=" * 60)
    print(f"\nEntry EV:        {fmt_mm(entry_ev)}  @ {entry_mult}x LTM EBITDA")
    print(f"Entry EBITDA:    {fmt_mm(ebitda_ltm)}")
    print(f"Entry Debt:      {fmt_mm(entry_debt)}")
    print(f"Entry Equity:    {fmt_mm(entry_equity)}")
    print(f"\nExit EV:         {fmt_mm(exit_result['exit_ev'])}  @ {tx['exit_multiple']}x Y5 EBITDA")
    print(f"Exit Equity:     {fmt_mm(exit_result['exit_equity'])}")
    print(f"Net Debt (Y5):   {fmt_mm(exit_result['net_debt'])}")
    print(f"\nIRR:             {fmt_pct(exit_result['irr'])}")
    print(f"MOIC:            {fmt_x(exit_result['moic'])}")
    print("\n" + "=" * 60)
    print("Outputs saved to outputs/")
    print("  projected_is.csv, projected_bs.csv, projected_cf.csv")
    print("  debt_schedule.csv, equity_returns.csv")
    print("  sensitivity_irr.csv, sensitivity_moic.csv")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
