"""Debt schedules: TLB, Revolver, cash waterfall (FCF -> mandatory -> sweep -> revolver)."""

from __future__ import annotations

import pandas as pd


def init_debt(entry_debt: float, assumptions: dict) -> dict:
    """Initialize debt structure from entry assumptions."""
    debt_cfg = assumptions.get("debt", {})
    rev_limit = float(debt_cfg.get("revolver", {}).get("limit", 0))
    tlb_pct = 0.75  # assume 75% TLB, 25% revolver of total debt
    tlb = entry_debt * tlb_pct
    rev_drawn = max(0.0, entry_debt - tlb)
    return {
        "tlb_bop": tlb,
        "rev_bop": rev_drawn,
        "rev_limit": rev_limit,
    }


def run_debt_schedule(
    ops_df: pd.DataFrame,
    assumptions: dict,
    entry_debt: float,
    min_cash: float,
    entry_equity: float,
) -> pd.DataFrame:
    """
    Cash waterfall: FCF -> mandatory amort -> maintain min cash -> revolver paydown -> TLB sweep.
    Output columns: year, cash_bop, fcf, interest, mandatory_amort, optional_paydown,
    revolver_draw, revolver_repay, cash_eop, tlb_bop, tlb_eop, rev_bop, rev_eop
    """
    debt_cfg = assumptions.get("debt", {})
    tlb_cfg = debt_cfg.get("tlb", {})
    rev_cfg = debt_cfg.get("revolver", {})
    tlb_rate = float(tlb_cfg.get("rate", 0.085))
    rev_rate = float(rev_cfg.get("rate", 0.08))
    amort_pct = float(tlb_cfg.get("amort_pct", 0.01))
    rev_limit = float(rev_cfg.get("limit", 800_000_000))

    init = init_debt(entry_debt, assumptions)
    tlb_bal = init["tlb_bop"]
    rev_bal = init["rev_bop"]
    cash = min_cash  # start with min cash (from equity funded)

    rows = []
    for _, row in ops_df.iterrows():
        year = int(row["year"])
        fcf = float(row["fcf"])

        cash_bop = cash
        tlb_bop = tlb_bal
        rev_bop = rev_bal

        interest_tlb = tlb_bop * tlb_rate
        interest_rev = rev_bop * rev_rate
        interest = interest_tlb + interest_rev

        mandatory_amort = tlb_bop * amort_pct
        optional_paydown = 0.0
        revolver_draw = 0.0
        revolver_repay = 0.0

        available = cash_bop + fcf - interest - mandatory_amort

        if available < min_cash:
            need = min_cash - available
            if rev_bal > 0:
                revolver_draw = min(need, rev_limit - rev_bal)
                rev_bal += revolver_draw
                available += revolver_draw
                revolver_draw = -revolver_draw
            cash = min_cash if available >= min_cash else available
        else:
            cash = min_cash
            excess = available - min_cash
            if rev_bal > 0 and excess > 0:
                revolver_repay = min(excess, rev_bal)
                rev_bal -= revolver_repay
                excess -= revolver_repay
            if excess > 0 and tlb_bal > 0:
                optional_paydown = min(excess, tlb_bal)
                tlb_bal -= optional_paydown
                excess -= optional_paydown
            if excess > 0:
                cash = min_cash + excess

        tlb_bal = max(0.0, tlb_bal - mandatory_amort)

        rows.append({
            "year": year,
            "cash_bop": cash_bop,
            "fcf": fcf,
            "interest": interest,
            "mandatory_amort": mandatory_amort,
            "optional_paydown": optional_paydown,
            "revolver_draw": -revolver_draw if revolver_draw < 0 else 0.0,
            "revolver_repay": revolver_repay,
            "cash_eop": cash,
            "tlb_bop": tlb_bop,
            "tlb_eop": tlb_bal,
            "rev_bop": rev_bop,
            "rev_eop": rev_bal,
        })

    return pd.DataFrame(rows)


def run_debt_schedule_fixed(
    ops_df: pd.DataFrame,
    debt_assump: dict,
    min_cash: float,
    tlb_bop: float,
    rev_bop: float,
) -> pd.DataFrame:
    """Run debt schedule with given beginning TLB and revolver balances."""
    tlb_cfg = debt_assump.get("tlb", {})
    rev_cfg = debt_assump.get("revolver", {})
    tlb_rate = float(tlb_cfg.get("rate", 0.085))
    rev_rate = float(rev_cfg.get("rate", 0.08))
    amort_pct = float(tlb_cfg.get("amort_pct", 0.01))
    rev_limit = float(rev_cfg.get("limit", 800_000_000))

    tlb_bal = tlb_bop
    rev_bal = rev_bop
    cash = min_cash

    rows = []
    for _, row in ops_df.iterrows():
        year = int(row["year"])
        fcf = float(row["fcf"])

        cash_bop = cash
        tlb_bop_y = tlb_bal
        rev_bop_y = rev_bal

        interest_tlb = tlb_bop_y * tlb_rate
        interest_rev = rev_bop_y * rev_rate
        interest = interest_tlb + interest_rev

        mandatory_amort = tlb_bop_y * amort_pct
        optional_paydown = 0.0
        revolver_draw = 0.0
        revolver_repay = 0.0

        available = cash_bop + fcf - interest - mandatory_amort

        if available < min_cash:
            need = min_cash - available
            if rev_bal < rev_limit:
                draw = min(need, rev_limit - rev_bal)
                rev_bal += draw
                revolver_draw = draw
                available += draw
            cash = min_cash if available >= min_cash else max(0.0, available)
        else:
            cash = min_cash
            excess = available - min_cash
            if rev_bal > 0 and excess > 0:
                repay = min(excess, rev_bal)
                revolver_repay = repay
                rev_bal -= repay
                excess -= repay
            if excess > 0 and tlb_bal > 0:
                optional_paydown = min(excess, tlb_bal)
                tlb_bal -= optional_paydown
                excess -= optional_paydown
            if excess > 0:
                cash = min_cash + excess

        tlb_bal = max(0.0, tlb_bal - mandatory_amort)

        rows.append({
            "year": year,
            "cash_bop": cash_bop,
            "fcf": fcf,
            "interest": interest,
            "mandatory_amort": mandatory_amort,
            "optional_paydown": optional_paydown,
            "revolver_draw": revolver_draw,
            "revolver_repay": revolver_repay,
            "cash_eop": cash,
            "tlb_bop": tlb_bop_y,
            "tlb_eop": tlb_bal,
            "rev_bop": rev_bop_y,
            "rev_eop": rev_bal,
        })

    return pd.DataFrame(rows)
