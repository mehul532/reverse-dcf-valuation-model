"""Command line interface for the reverse DCF toolkit."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer

from reversedcf.dcf import DCFInputs, enterprise_value, run_dcf
from reversedcf.metrics import format_currency, format_percent
from reversedcf.report import generate_markdown_report
from reversedcf.reverse import solve_required_revenue_cagr

app = typer.Typer(help="Reverse DCF valuation toolkit.")


@app.command("run-case-study")
def run_case_study(
    ticker: str = typer.Option("AAPL", "--ticker", "-t", help="Ticker to run."),
) -> None:
    """Run one of the bundled case study scripts."""

    script = Path("scripts") / f"run_{ticker.lower()}_case_study.py"
    if not script.exists():
        raise typer.BadParameter(
            f"No bundled case study exists for {ticker.upper()}. "
            "Use generate-report with a manual JSON file."
        )
    raise typer.Exit(subprocess.call([sys.executable, str(script)]))


@app.command("solve-growth")
def solve_growth(
    target_enterprise_value: float = typer.Option(..., help="Target market enterprise value."),
    current_revenue: float = typer.Option(..., help="Most recent revenue."),
    fcf_margin: float = typer.Option(..., help="FCF margin as decimal, e.g. 0.25."),
    wacc: float = typer.Option(0.08, help="WACC as decimal."),
    terminal_growth: float = typer.Option(0.025, help="Terminal growth as decimal."),
    net_debt: float = typer.Option(0.0, help="Net debt, debt minus cash."),
    shares_outstanding: float = typer.Option(1.0, help="Diluted shares outstanding."),
    forecast_years: int = typer.Option(5, help="Explicit forecast period."),
) -> None:
    """Solve for revenue CAGR implied by a target enterprise value."""

    inputs = DCFInputs(
        current_revenue=current_revenue,
        revenue_cagr=0.05,
        fcf_margin=fcf_margin,
        forecast_years=forecast_years,
        wacc=wacc,
        terminal_growth=terminal_growth,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )
    required_growth = solve_required_revenue_cagr(target_enterprise_value, inputs)
    valuation = run_dcf(DCFInputs(**{**inputs.__dict__, "revenue_cagr": required_growth}))
    typer.echo(f"Required revenue CAGR: {format_percent(required_growth)}")
    typer.echo(f"Model enterprise value: {format_currency(valuation.enterprise_value)}")


@app.command("generate-report")
def generate_report(
    input_path: Path = typer.Option(
        Path("data/sample_inputs/aapl.json"),
        "--input",
        "-i",
        help="Manual JSON or CSV input file.",
    ),
    output_path: Path = typer.Option(
        Path("reports/sample_report.md"), "--output", "-o", help="Report output path."
    ),
) -> None:
    """Generate a markdown report from a manual input file."""

    from scripts.generate_report import build_report

    path = build_report(input_path=input_path, output_path=output_path)
    typer.echo(f"Wrote {path}")


@app.command("launch-app")
def launch_app() -> None:
    """Launch the Streamlit dashboard."""

    raise typer.Exit(
        subprocess.call([sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py"])
    )


if __name__ == "__main__":
    app()
