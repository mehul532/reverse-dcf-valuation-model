"""Reverse DCF solvers for market-implied assumptions."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

from scipy.optimize import brentq

from reversedcf.dcf import DCFInputs, enterprise_value


class ReverseDCFError(ValueError):
    """Raised when a reverse DCF assumption cannot be solved."""


def _solve_assumption(
    target_enterprise_value: float,
    base_inputs: DCFInputs,
    field: str,
    lower: float,
    upper: float,
    validator: Callable[[DCFInputs], None] | None = None,
) -> float:
    if target_enterprise_value <= 0:
        raise ValueError("target_enterprise_value must be positive.")
    if lower >= upper:
        raise ValueError("lower must be less than upper.")

    def objective(value: float) -> float:
        candidate = replace(base_inputs, **{field: value})
        if validator is not None:
            validator(candidate)
        return enterprise_value(candidate) - target_enterprise_value

    try:
        return float(brentq(objective, lower, upper, xtol=1e-10, rtol=1e-10))
    except ValueError as exc:
        lower_value = _safe_objective_value(objective, lower)
        upper_value = _safe_objective_value(objective, upper)
        raise ReverseDCFError(
            "No reverse DCF solution found for "
            f"{field!r} between {lower:.4f} and {upper:.4f}. "
            "Check whether the target enterprise value is bracketed by the "
            f"model values at the endpoints. Endpoint objective values: "
            f"lower={lower_value}, upper={upper_value}."
        ) from exc


def _safe_objective_value(objective: Callable[[float], float], value: float) -> str:
    try:
        return f"{objective(value):.4f}"
    except Exception as exc:  # pragma: no cover - defensive error message path
        return f"error: {exc}"


def solve_required_revenue_cagr(
    target_enterprise_value: float,
    base_inputs: DCFInputs,
    lower: float = -0.20,
    upper: float = 0.50,
) -> float:
    """Solve for the revenue CAGR required to match target enterprise value."""

    return _solve_assumption(
        target_enterprise_value, base_inputs, "revenue_cagr", lower, upper
    )


def solve_required_fcf_margin(
    target_enterprise_value: float,
    base_inputs: DCFInputs,
    lower: float = 0.01,
    upper: float = 0.80,
) -> float:
    """Solve for the FCF margin required to match target enterprise value."""

    return _solve_assumption(
        target_enterprise_value, base_inputs, "fcf_margin", lower, upper
    )


def solve_required_wacc(
    target_enterprise_value: float,
    base_inputs: DCFInputs,
    lower: float = 0.03,
    upper: float = 0.20,
) -> float:
    """Solve for the WACC that makes the DCF match target enterprise value."""

    return _solve_assumption(target_enterprise_value, base_inputs, "wacc", lower, upper)


def solve_required_terminal_growth(
    target_enterprise_value: float,
    base_inputs: DCFInputs,
    lower: float = -0.02,
    upper: float = 0.05,
) -> float:
    """Solve for terminal growth required to match target enterprise value."""

    return _solve_assumption(
        target_enterprise_value, base_inputs, "terminal_growth", lower, upper
    )
