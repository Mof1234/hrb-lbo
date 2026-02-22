"""Shared utilities."""

from __future__ import annotations


def fmt_mm(x: float) -> str:
    """Format as USD mm."""
    if x is None or (isinstance(x, float) and x != x):  # nan
        return "n/a"
    return f"${x / 1e6:,.1f}"


def fmt_pct(x: float) -> str:
    """Format as percent."""
    if x is None or (isinstance(x, float) and x != x):
        return "n/a"
    return f"{x * 100:.1f}%"


def fmt_x(x: float) -> str:
    """Format as multiple (e.g. 2.5x)."""
    if x is None or (isinstance(x, float) and x != x):
        return "n/a"
    return f"{x:.2f}x"
