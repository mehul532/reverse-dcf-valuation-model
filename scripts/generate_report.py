"""Generate reverse DCF markdown reports from manual input files."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from reversedcf.data import ManualInputs, load_manual_inputs
from reversedcf.dcf import DCFInputs, run_dcf
from reversedcf.financials import compare_implied_to_history
from reversedcf.plotting import (
    plot_fcf_forecast,
    plot_implied_vs_historical,
    plot_revenue_forecast,
    plot_scenario_prices,
    plot_sensitivity_heatmap,
)
from reversedcf.report import generate_markdown_report
from reversedcf.reverse import (
    solve_required_fcf_margin,
    solve_required_revenue_cagr,
    solve_required_terminal_growth,
    solve_required_wacc,
)
from reversedcf.scenarios import Scenario, market_implied_scenario, run_scenarios
from reversedcf.sensitivity import sensitivity_table_share_price


def build_report(
    input_path: str | Path,
    output_path: str | Path,
    revenue_cagr: float = 0.08,
    wacc: float = 0.08,
    terminal_growth: float = 0.025,
    forecast_years: int = 5,
    historical_growth: float | None = None,
    historical_margin: float | None = None,
) -> Path:
    """Build report, figures, scenarios, and sensitivity outputs."""

    manual = load_manual_inputs(input_path)
    base_inputs = _manual_to_dcf_inputs(
        manual,
        revenue_cagr=revenue_cagr,
        wacc=wacc,
        terminal_growth=terminal_growth,
        forecast_years=forecast_years,
    )
    valuation = run_dcf(base_inputs)
    reverse_results = _reverse_results(manual.enterprise_value, base_inputs)
    scenario_results = _scenario_results(manual, base_inputs)
    sensitivity = sensitivity_table_share_price(
        base_inputs,
        wacc_values=[wacc - 0.01, wacc, wacc + 0.01],
        terminal_growth_values=[
            terminal_growth - 0.005,
            terminal_growth,
            terminal_growth + 0.005,
        ],
    )

    prefix = Path(output_path).stem.replace("_reverse_dcf_report", "")
    figure_dir = ROOT / "reports" / "figures"
    plot_revenue_forecast(
        valuation.projection, figure_dir / f"{prefix}_revenue_forecast.png"
    )
    plot_fcf_forecast(valuation.projection, figure_dir / f"{prefix}_fcf_forecast.png")
    plot_sensitivity_heatmap(
        sensitivity,
        f"{manual.ticker} Implied Share Price Sensitivity",
        figure_dir / f"{prefix}_sensitivity_heatmap.png",
    )
    plot_scenario_prices(
        scenario_results, figure_dir / f"{prefix}_scenario_prices.png"
    )

    implied_growth = reverse_results.get("Required revenue CAGR")
    implied_margin = reverse_results.get("Required FCF margin")
    historical_comparison = None
    if isinstance(implied_growth, float) and isinstance(implied_margin, float):
        historical_comparison = compare_implied_to_history(
            implied_growth=implied_growth,
            historical_growth=historical_growth
            if historical_growth is not None
            else max(revenue_cagr - 0.02, -0.95),
            implied_margin=implied_margin,
            historical_margin=historical_margin
            if historical_margin is not None
            else manual.fcf_margin,
        )
        plot_implied_vs_historical(
            implied={
                "Revenue CAGR": historical_comparison["implied_growth"],
                "FCF Margin": historical_comparison["implied_margin"],
            },
            historical={
                "Revenue CAGR": historical_comparison["historical_growth"],
                "FCF Margin": historical_comparison["historical_margin"],
            },
            output_path=figure_dir / f"{prefix}_implied_vs_historical.png",
        )

    return generate_markdown_report(
        ticker=manual.ticker,
        company_name=manual.company_name,
        base_inputs=base_inputs,
        reverse_results=reverse_results,
        scenario_results=scenario_results,
        output_path=output_path,
        sensitivity_table=sensitivity,
        historical_comparison=historical_comparison,
        current_share_price=manual.current_share_price,
        target_enterprise_value=manual.enterprise_value,
    )


def _manual_to_dcf_inputs(
    manual: ManualInputs,
    revenue_cagr: float,
    wacc: float,
    terminal_growth: float,
    forecast_years: int,
) -> DCFInputs:
    return DCFInputs(
        current_revenue=manual.current_revenue,
        revenue_cagr=revenue_cagr,
        fcf_margin=manual.fcf_margin,
        forecast_years=forecast_years,
        wacc=wacc,
        terminal_growth=terminal_growth,
        net_debt=manual.net_debt,
        shares_outstanding=manual.shares_outstanding,
    )


def _reverse_results(target_enterprise_value: float, base_inputs: DCFInputs) -> dict[str, Any]:
    solvers = {
        "Required revenue CAGR": solve_required_revenue_cagr,
        "Required FCF margin": solve_required_fcf_margin,
        "Required WACC": solve_required_wacc,
        "Required terminal growth": solve_required_terminal_growth,
    }
    results: dict[str, Any] = {}
    for label, solver in solvers.items():
        try:
            results[label] = solver(target_enterprise_value, base_inputs)
        except Exception as exc:
            results[label] = exc
    return results


def _scenario_results(manual: ManualInputs, base_inputs: DCFInputs):
    scenarios = [
        Scenario(
            "Bear",
            replace(
                base_inputs,
                revenue_cagr=max(base_inputs.revenue_cagr - 0.04, -0.95),
                fcf_margin=max(base_inputs.fcf_margin - 0.03, -0.95),
                wacc=base_inputs.wacc + 0.01,
                terminal_growth=base_inputs.terminal_growth - 0.005,
            ),
        ),
        Scenario("Base", base_inputs),
        Scenario(
            "Bull",
            replace(
                base_inputs,
                revenue_cagr=base_inputs.revenue_cagr + 0.04,
                fcf_margin=base_inputs.fcf_margin + 0.03,
                wacc=max(base_inputs.wacc - 0.01, base_inputs.terminal_growth + 0.001),
                terminal_growth=base_inputs.terminal_growth + 0.005,
            ),
        ),
    ]
    try:
        scenarios.append(market_implied_scenario(manual.enterprise_value, base_inputs))
    except Exception:
        pass
    return run_scenarios(scenarios, current_share_price=manual.current_share_price)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="data/sample_inputs/aapl.json",
        help="Manual input JSON or CSV path.",
    )
    parser.add_argument(
        "--output",
        default="reports/sample_report.md",
        help="Markdown report output path.",
    )
    parser.add_argument("--revenue-cagr", type=float, default=0.08)
    parser.add_argument("--wacc", type=float, default=0.08)
    parser.add_argument("--terminal-growth", type=float, default=0.025)
    parser.add_argument("--forecast-years", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = build_report(
        input_path=args.input,
        output_path=args.output,
        revenue_cagr=args.revenue_cagr,
        wacc=args.wacc,
        terminal_growth=args.terminal_growth,
        forecast_years=args.forecast_years,
    )
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
