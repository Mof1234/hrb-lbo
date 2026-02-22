"""Sensitivity: Entry Multiple x Exit Multiple -> IRR, MOIC grids."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .debt import init_debt, run_debt_schedule_fixed
from .operating_model import project_operations
from .returns import compute_exit


def run_sensitivity(
    base_inputs: dict,
    entry_grid: list[float],
    exit_grid: list[float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run LBO for each (entry_mult, exit_mult) and return irr_df, moic_df.
    base_inputs: {normalized_ebitda_ltm, base_revenue, base_year, assumptions}
    """
    irr_grid = np.full((len(exit_grid), len(entry_grid)), np.nan)
    moic_grid = np.full((len(exit_grid), len(entry_grid)), np.nan)

    assumptions = base_inputs["assumptions"].copy()
    tx = assumptions["transaction"]
    base_revenue = base_inputs["base_revenue"]
    base_year = base_inputs["base_year"]
    ebitda_ltm = base_inputs["normalized_ebitda_ltm"]
    min_cash = float(tx.get("min_cash", 200_000_000))
    fees_pct = float(tx.get("fees_pct_ev", 0.02))
    debt_pct = float(tx.get("debt_pct_ev", 0.60))

    for j, entry_mult in enumerate(entry_grid):
        entry_ev = entry_mult * ebitda_ltm
        fees = fees_pct * entry_ev
        total_uses = entry_ev + fees
        entry_debt = debt_pct * total_uses
        entry_equity = total_uses - entry_debt

        ops_df = project_operations(base_revenue, base_year, assumptions)
        debt_df = run_debt_schedule_fixed(
            ops_df,
            assumptions["debt"],
            min_cash,
            init_debt(entry_debt, assumptions)["tlb_bop"],
            init_debt(entry_debt, assumptions)["rev_bop"],
        )

        for i, exit_mult in enumerate(exit_grid):
            assumptions["transaction"] = {**tx, "exit_multiple": exit_mult}
            res = compute_exit(ops_df, debt_df, assumptions, entry_equity)
            irr_grid[i, j] = res["irr"]
            moic_grid[i, j] = res["moic"]

    irr_df = pd.DataFrame(irr_grid, index=exit_grid, columns=entry_grid)
    moic_df = pd.DataFrame(moic_grid, index=exit_grid, columns=entry_grid)
    irr_df.index.name = "exit_mult"
    irr_df.columns.name = "entry_mult"
    moic_df.index.name = "exit_mult"
    moic_df.columns.name = "entry_mult"
    return irr_df, moic_df
