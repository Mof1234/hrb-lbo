"""Exit valuation and IRR/MOIC computation."""

from __future__ import annotations


def _npv(rate: float, cashflows: list[float]) -> float:
    return sum(c / (1 + rate) ** i for i, c in enumerate(cashflows))


def compute_exit(
    ops_df: "pd.DataFrame",
    debt_df: "pd.DataFrame",
    assumptions: dict,
    initial_equity: float,
) -> dict:
    """
    Compute exit equity value, MOIC, IRR.
    Returns dict with exit_ev, exit_equity, net_debt, moic, irr.
    """
    import pandas as pd

    exit_mult = float(assumptions.get("transaction", {}).get("exit_multiple", 9.0))
    tax_rate = float(assumptions.get("model", {}).get("tax_rate", 0.24))

    last_ops = ops_df.iloc[-1]
    last_debt = debt_df.iloc[-1]
    ebitda_y5 = float(last_ops["ebitda"])
    exit_ev = exit_mult * ebitda_y5

    total_debt = float(last_debt["tlb_eop"]) + float(last_debt["rev_eop"])
    cash = float(last_debt["cash_eop"])
    net_debt = total_debt - cash
    exit_equity = exit_ev - net_debt

    moic = compute_moic(initial_equity, exit_equity)

    cashflows = [-initial_equity]
    for _ in range(4):
        cashflows.append(0.0)
    cashflows.append(exit_equity)
    irr = compute_irr(cashflows)

    return {
        "exit_ev": exit_ev,
        "exit_equity": exit_equity,
        "net_debt": net_debt,
        "total_debt": total_debt,
        "cash": cash,
        "ebitda_y5": ebitda_y5,
        "moic": moic,
        "irr": irr,
    }


def compute_irr(cashflows: list[float]) -> float:
    """IRR for [-eq, 0,0,0,0, exit] cashflow pattern (5-year hold)."""
    cf = list(cashflows)
    if len(cf) < 2 or cf[0] >= 0:
        return float("nan")
    lo, hi = -0.99, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        npv = _npv(mid, cf)
        if abs(npv) < 1e-6:
            return float(mid)
        if npv > 0:
            lo = mid
        else:
            hi = mid
    return float((lo + hi) / 2)


def compute_moic(initial_equity: float, exit_equity: float) -> float:
    """MOIC = exit_equity / initial_equity."""
    if initial_equity <= 0:
        return float("nan")
    return exit_equity / initial_equity
