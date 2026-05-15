"""Sensitivity analysis helpers."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from reversedcf.dcf import DCFInputs, implied_share_price
from reversedcf.reverse import (
    ReverseDCFError,
    solve_required_fcf_margin,
    solve_required_revenue_cagr,
)


def _percent_label(value: float) -> str:
    return f"{value:.1%}"


def sensitivity_table_share_price(
    base_inputs: DCFInputs,
    wacc_values: list[float],
    terminal_growth_values: list[float],
) -> pd.DataFrame:
    """Return implied share price across WACC and terminal growth assumptions."""

    table = pd.DataFrame(
        index=[_percent_label(wacc) for wacc in wacc_values],
        columns=[_percent_label(growth) for growth in terminal_growth_values],
        dtype=float,
    )
    table.index.name = "WACC"
    table.columns.name = "Terminal Growth"

    for wacc in wacc_values:
        for terminal_growth in terminal_growth_values:
            try:
                inputs = replace(
                    base_inputs, wacc=wacc, terminal_growth=terminal_growth
                )
                value = implied_share_price(inputs)
            except ValueError:
                value = float("nan")
            table.loc[_percent_label(wacc), _percent_label(terminal_growth)] = value
    return table


def sensitivity_table_required_growth(
    target_enterprise_value: float,
    base_inputs: DCFInputs,
    wacc_values: list[float],
    fcf_margin_values: list[float],
) -> pd.DataFrame:
    """Return required revenue CAGR across WACC and FCF margin assumptions."""

    table = pd.DataFrame(
        index=[_percent_label(wacc) for wacc in wacc_values],
        columns=[_percent_label(margin) for margin in fcf_margin_values],
        dtype=float,
    )
    table.index.name = "WACC"
    table.columns.name = "FCF Margin"

    for wacc in wacc_values:
        for fcf_margin in fcf_margin_values:
            inputs = replace(base_inputs, wacc=wacc, fcf_margin=fcf_margin)
            try:
                value = solve_required_revenue_cagr(target_enterprise_value, inputs)
            except ReverseDCFError:
                value = float("nan")
            table.loc[_percent_label(wacc), _percent_label(fcf_margin)] = value
    return table


def sensitivity_table_required_margin(
    target_enterprise_value: float,
    base_inputs: DCFInputs,
    wacc_values: list[float],
    growth_values: list[float],
) -> pd.DataFrame:
    """Return required FCF margin across WACC and revenue growth assumptions."""

    table = pd.DataFrame(
        index=[_percent_label(wacc) for wacc in wacc_values],
        columns=[_percent_label(growth) for growth in growth_values],
        dtype=float,
    )
    table.index.name = "WACC"
    table.columns.name = "Revenue CAGR"

    for wacc in wacc_values:
        for growth in growth_values:
            inputs = replace(base_inputs, wacc=wacc, revenue_cagr=growth)
            try:
                value = solve_required_fcf_margin(target_enterprise_value, inputs)
            except ReverseDCFError:
                value = float("nan")
            table.loc[_percent_label(wacc), _percent_label(growth)] = value
    return table
