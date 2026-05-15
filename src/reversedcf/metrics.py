"""Formatting and basic finance metrics."""

from __future__ import annotations


def format_percent(x: float) -> str:
    """Format a decimal percentage."""

    return f"{x:.1%}"


def format_currency(x: float) -> str:
    """Format a currency amount with compact large-number suffixes."""

    abs_value = abs(x)
    sign = "-" if x < 0 else ""
    if abs_value >= 1_000_000_000_000:
        return f"{sign}${abs_value / 1_000_000_000_000:.2f}T"
    if abs_value >= 1_000_000_000:
        return f"{sign}${abs_value / 1_000_000_000:.2f}B"
    if abs_value >= 1_000_000:
        return f"{sign}${abs_value / 1_000_000:.2f}M"
    return f"{sign}${abs_value:,.2f}"


def revenue_cagr(start: float, end: float, years: int) -> float:
    """Calculate revenue CAGR from start and end revenue."""

    if start <= 0 or end <= 0:
        raise ValueError("start and end revenue must be positive.")
    if years <= 0:
        raise ValueError("years must be positive.")
    return (end / start) ** (1 / years) - 1


def margin(fcf: float, revenue: float) -> float:
    """Calculate free cash flow margin."""

    if revenue == 0:
        raise ValueError("revenue must not be zero.")
    return fcf / revenue
