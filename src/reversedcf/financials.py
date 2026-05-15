"""Financial statement helper functions."""

from __future__ import annotations

from collections.abc import Sequence


def historical_revenue_cagr(revenues: Sequence[float]) -> float:
    """Calculate historical revenue CAGR from an ordered revenue series."""

    values = [float(value) for value in revenues if value is not None]
    if len(values) < 2:
        raise ValueError("At least two revenue observations are required.")
    start, end = values[0], values[-1]
    if start <= 0 or end <= 0:
        raise ValueError("Revenue values used for CAGR must be positive.")
    years = len(values) - 1
    return (end / start) ** (1 / years) - 1


def average_margin(values: Sequence[float]) -> float:
    """Return arithmetic average margin from decimal margin values."""

    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        raise ValueError("At least one margin value is required.")
    return sum(numbers) / len(numbers)


def latest_value(series: Sequence[float]) -> float:
    """Return the most recent non-null value in a sequence."""

    for value in reversed(series):
        if value is not None:
            return float(value)
    raise ValueError("No non-null values found.")


def compare_implied_to_history(
    implied_growth: float,
    historical_growth: float,
    implied_margin: float,
    historical_margin: float,
) -> dict[str, float]:
    """Compare market-implied growth and margin with historical performance."""

    return {
        "implied_growth": implied_growth,
        "historical_growth": historical_growth,
        "growth_spread": implied_growth - historical_growth,
        "implied_margin": implied_margin,
        "historical_margin": historical_margin,
        "margin_spread": implied_margin - historical_margin,
    }
