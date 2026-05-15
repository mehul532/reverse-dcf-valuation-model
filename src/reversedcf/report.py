"""Markdown report generation for reverse DCF case studies."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from reversedcf.dcf import DCFInputs, run_dcf
from reversedcf.metrics import format_currency, format_percent
from reversedcf.scenarios import ScenarioResult


def generate_markdown_report(
    ticker: str,
    company_name: str,
    base_inputs: DCFInputs,
    reverse_results: Mapping[str, Any],
    scenario_results: Sequence[ScenarioResult],
    output_path: str | Path,
    sensitivity_table: pd.DataFrame | None = None,
    historical_comparison: Mapping[str, float] | None = None,
    current_share_price: float | None = None,
    target_enterprise_value: float | None = None,
) -> Path:
    """Generate a stock pitch-style markdown report."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    valuation = run_dcf(base_inputs)

    lines = [
        f"# {company_name} ({ticker.upper()}) Reverse DCF Valuation",
        "",
        "> Educational valuation model only. This report is not financial advice, "
        "does not predict stock prices, and should not be treated as an investment "
        "recommendation.",
        "",
        "## Executive Summary",
        "",
        (
            f"The base case DCF produces an enterprise value of "
            f"{format_currency(valuation.enterprise_value)} and an implied share "
            f"price of {format_currency(valuation.implied_share_price)}."
        ),
    ]

    if target_enterprise_value is not None:
        lines.append(
            f"The observed market enterprise value used for the reverse DCF is "
            f"{format_currency(target_enterprise_value)}."
        )
    if current_share_price is not None:
        lines.append(f"The observed share price used in the analysis is {format_currency(current_share_price)}.")

    lines.extend(
        [
            "",
            "## Current Valuation",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| Current revenue | {format_currency(base_inputs.current_revenue)} |",
            f"| Base revenue CAGR | {format_percent(base_inputs.revenue_cagr)} |",
            f"| Base FCF margin | {format_percent(base_inputs.fcf_margin)} |",
            f"| WACC | {format_percent(base_inputs.wacc)} |",
            f"| Terminal growth | {format_percent(base_inputs.terminal_growth)} |",
            f"| Net debt | {format_currency(base_inputs.net_debt)} |",
            f"| Shares outstanding | {base_inputs.shares_outstanding:,.0f} |",
            "",
            "## Market-Implied Assumptions",
            "",
            "| Solved assumption | Result |",
            "| --- | ---: |",
        ]
    )

    for label, value in reverse_results.items():
        lines.append(f"| {label} | {_format_reverse_result(value)} |")

    lines.extend(
        [
            "",
            "## Scenario Analysis",
            "",
            "| Scenario | EV | Equity Value | Implied Price | Upside / Downside | Revenue CAGR | FCF Margin | WACC | Terminal Growth |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for result in scenario_results:
        upside = (
            "n/a"
            if result.upside_downside is None
            else format_percent(result.upside_downside)
        )
        lines.append(
            "| "
            f"{result.name} | "
            f"{format_currency(result.enterprise_value)} | "
            f"{format_currency(result.equity_value)} | "
            f"{format_currency(result.implied_share_price)} | "
            f"{upside} | "
            f"{format_percent(result.revenue_cagr)} | "
            f"{format_percent(result.fcf_margin)} | "
            f"{format_percent(result.wacc)} | "
            f"{format_percent(result.terminal_growth)} |"
        )

    lines.extend(["", "## Sensitivity Analysis", ""])
    if sensitivity_table is not None:
        lines.append(_dataframe_to_markdown(sensitivity_table.round(2)))
    else:
        lines.append("Sensitivity tables can be generated from WACC, terminal growth, growth, and margin ranges.")

    lines.extend(["", "## Historical Comparison", ""])
    if historical_comparison:
        lines.extend(
            [
                "| Metric | Value |",
                "| --- | ---: |",
                f"| Historical revenue growth | {format_percent(historical_comparison.get('historical_growth', 0.0))} |",
                f"| Market-implied revenue growth | {format_percent(historical_comparison.get('implied_growth', 0.0))} |",
                f"| Growth spread | {format_percent(historical_comparison.get('growth_spread', 0.0))} |",
                f"| Historical FCF margin | {format_percent(historical_comparison.get('historical_margin', 0.0))} |",
                f"| Market-implied FCF margin | {format_percent(historical_comparison.get('implied_margin', 0.0))} |",
                f"| Margin spread | {format_percent(historical_comparison.get('margin_spread', 0.0))} |",
            ]
        )
    else:
        lines.append(
            "A robust equity research workflow should compare implied assumptions "
            "against historical revenue growth, margin progression, reinvestment "
            "needs, and business quality."
        )

    lines.extend(
        [
            "",
            "## Key Limitations",
            "",
            "- The model is highly sensitive to WACC, terminal value, and margin assumptions.",
            "- A single-stage constant-growth DCF cannot fully capture product cycles, cyclicality, dilution, buybacks, or capital intensity changes.",
            "- Market value inputs can change quickly and may not match live data at the time this report is read.",
            "- Reverse DCF outputs describe assumptions implied by the selected inputs; they are not proof that a security is undervalued or overvalued.",
            "- This project is for education and portfolio demonstration only, not investment advice.",
            "",
        ]
    )

    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def _format_reverse_result(value: Any) -> str:
    if isinstance(value, Exception):
        return f"Not solved: {value}"
    if isinstance(value, str):
        return value
    return format_percent(float(value))


def _dataframe_to_markdown(df: pd.DataFrame) -> str:
    index_name = df.index.name or ""
    headers = [index_name] + [str(column) for column in df.columns]
    rows = []
    for index, row in df.iterrows():
        rows.append([str(index)] + [_format_table_cell(value) for value in row])

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] + ["---:"] * len(df.columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _format_table_cell(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if pd.isna(numeric):
        return "n/a"
    return f"{numeric:,.2f}"
