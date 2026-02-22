"""Load financials, assumptions, and mapping from disk."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


def load_financials(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load historical IS, BS, CF from data_dir."""
    data_dir = Path(data_dir)
    return {
        "is": pd.read_csv(data_dir / "historical_is.csv"),
        "bs": pd.read_csv(data_dir / "historical_bs.csv"),
        "cf": pd.read_csv(data_dir / "historical_cf.csv"),
    }


def load_assumptions(path: str | Path) -> dict:
    """Load assumptions.yaml."""
    with open(path) as f:
        return yaml.safe_load(f)


def load_adjustments(path: str | Path) -> dict:
    """Load mapping.yaml (EBITDA addbacks/subtractions)."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("adjustments", {})
