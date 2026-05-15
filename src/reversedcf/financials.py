"""Financial statement helper functions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pandas as pd


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


def historical_revenue_cagr_from_series(revenues: Sequence[float]) -> float | None:
    """Return historical revenue CAGR, or None when insufficient data exists."""

    values = _clean_numeric_series(revenues)
    if len(values) < 2:
        return None
    if values[0] <= 0 or values[-1] <= 0:
        return None
    years = len(values) - 1
    return (values[-1] / values[0]) ** (1 / years) - 1


def historical_average_fcf_margin(
    revenues: Sequence[float], free_cash_flows: Sequence[float]
) -> dict[str, float] | None:
    """Return average/min/max historical FCF margin from revenue and FCF series."""

    revenue_values = _clean_numeric_series(revenues)
    fcf_values = _clean_numeric_series(free_cash_flows)
    pair_count = min(len(revenue_values), len(fcf_values))
    if pair_count == 0:
        return None

    margins = []
    for revenue, fcf in zip(
        revenue_values[-pair_count:], fcf_values[-pair_count:], strict=False
    ):
        if revenue:
            margins.append(fcf / revenue)
    if not margins:
        return None

    return {
        "historical_average_fcf_margin": sum(margins) / len(margins),
        "historical_min_fcf_margin": min(margins),
        "historical_max_fcf_margin": max(margins),
    }


def build_historical_comparison_table(
    *,
    implied_revenue_cagr: float | None,
    current_fcf_margin: float | None,
    historical_revenues: Sequence[float] | None = None,
    historical_free_cash_flows: Sequence[float] | None = None,
    historical_fcf_margins: Sequence[float] | None = None,
) -> pd.DataFrame:
    """Build a compact comparison of implied/current assumptions vs history."""

    rows: list[dict[str, Any]] = []
    historical_growth = historical_revenue_cagr_from_series(historical_revenues or [])
    rows.append(
        {
            "Metric": "Revenue CAGR",
            "Current / Implied": implied_revenue_cagr,
            "Historical": historical_growth,
            "Spread": _spread(implied_revenue_cagr, historical_growth),
        }
    )

    margin_stats = None
    clean_margins = _clean_numeric_series(historical_fcf_margins or [])
    if clean_margins:
        margin_stats = {
            "historical_average_fcf_margin": sum(clean_margins) / len(clean_margins),
            "historical_min_fcf_margin": min(clean_margins),
            "historical_max_fcf_margin": max(clean_margins),
        }
    elif historical_revenues and historical_free_cash_flows:
        margin_stats = historical_average_fcf_margin(
            historical_revenues, historical_free_cash_flows
        )

    historical_margin = (
        None if margin_stats is None else margin_stats["historical_average_fcf_margin"]
    )
    row = {
        "Metric": "FCF Margin",
        "Current / Implied": current_fcf_margin,
        "Historical": historical_margin,
        "Spread": _spread(current_fcf_margin, historical_margin),
    }
    if margin_stats is not None:
        row["Historical Min"] = margin_stats["historical_min_fcf_margin"]
        row["Historical Max"] = margin_stats["historical_max_fcf_margin"]
    rows.append(row)

    return pd.DataFrame(rows)


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


def _clean_numeric_series(values: Sequence[float] | None) -> list[float]:
    if values is None:
        return []
    clean_values = []
    for value in values:
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        clean_values.append(number)
    return clean_values


def _spread(current: float | None, historical: float | None) -> float | None:
    if current is None or historical is None:
        return None
    return current - historical
