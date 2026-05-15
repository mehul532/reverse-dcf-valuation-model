"""Command line interface for the reverse DCF toolkit."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

try:
    import typer
except ImportError:  # pragma: no cover - fallback for non-installed envs
    typer = None

from reversedcf.dcf import DCFInputs, run_dcf
from reversedcf.metrics import format_currency, format_percent
from reversedcf.reverse import solve_required_revenue_cagr


def _run_case_study_impl(ticker: str) -> int:
    script = Path("scripts") / f"run_{ticker.lower()}_case_study.py"
    if not script.exists():
        raise ValueError(
            f"No bundled case study exists for {ticker.upper()}. "
            "Use generate-report with a manual JSON file."
        )
    return subprocess.call([sys.executable, str(script)])


def _solve_growth_impl(
    target_enterprise_value: float,
    current_revenue: float,
    fcf_margin: float,
    wacc: float,
    terminal_growth: float,
    net_debt: float,
    shares_outstanding: float,
    forecast_years: int,
) -> tuple[float, float]:
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
    valuation = run_dcf(replace(inputs, revenue_cagr=required_growth))
    return required_growth, valuation.enterprise_value


def _generate_report_impl(input_path: Path, output_path: Path) -> Path:
    from scripts.generate_report import build_report

    return build_report(input_path=input_path, output_path=output_path)


def _launch_app_impl() -> int:
    return subprocess.call([sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py"])


if typer is not None:
    app = typer.Typer(help="Reverse DCF valuation toolkit.")

    @app.command("run-case-study")
    def run_case_study(
        ticker: str = typer.Option("AAPL", "--ticker", "-t", help="Ticker to run."),
    ) -> None:
        """Run one of the bundled case study scripts."""

        try:
            raise typer.Exit(_run_case_study_impl(ticker))
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

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

        required_growth, model_ev = _solve_growth_impl(
            target_enterprise_value=target_enterprise_value,
            current_revenue=current_revenue,
            fcf_margin=fcf_margin,
            wacc=wacc,
            terminal_growth=terminal_growth,
            net_debt=net_debt,
            shares_outstanding=shares_outstanding,
            forecast_years=forecast_years,
        )
        typer.echo(f"Required revenue CAGR: {format_percent(required_growth)}")
        typer.echo(f"Model enterprise value: {format_currency(model_ev)}")

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

        path = _generate_report_impl(input_path=input_path, output_path=output_path)
        typer.echo(f"Wrote {path}")

    @app.command("launch-app")
    def launch_app() -> None:
        """Launch the Streamlit dashboard."""

        raise typer.Exit(_launch_app_impl())

else:
    app = None


def _fallback_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m reversedcf.cli",
        description=(
            "Reverse DCF valuation toolkit. Install requirements for the richer "
            "Typer interface."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run-case-study", help="Run a bundled case study.")
    run_parser.add_argument("--ticker", "-t", default="AAPL")

    solve_parser = subparsers.add_parser("solve-growth", help="Solve for required revenue CAGR.")
    solve_parser.add_argument("--target-enterprise-value", type=float, required=True)
    solve_parser.add_argument("--current-revenue", type=float, required=True)
    solve_parser.add_argument("--fcf-margin", type=float, required=True)
    solve_parser.add_argument("--wacc", type=float, default=0.08)
    solve_parser.add_argument("--terminal-growth", type=float, default=0.025)
    solve_parser.add_argument("--net-debt", type=float, default=0.0)
    solve_parser.add_argument("--shares-outstanding", type=float, default=1.0)
    solve_parser.add_argument("--forecast-years", type=int, default=5)

    report_parser = subparsers.add_parser("generate-report", help="Generate a markdown report.")
    report_parser.add_argument("--input", "-i", default="data/sample_inputs/aapl.json")
    report_parser.add_argument("--output", "-o", default="reports/sample_report.md")

    subparsers.add_parser("launch-app", help="Launch the Streamlit dashboard.")

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "run-case-study":
        return _run_case_study_impl(args.ticker)
    if args.command == "solve-growth":
        required_growth, model_ev = _solve_growth_impl(
            target_enterprise_value=args.target_enterprise_value,
            current_revenue=args.current_revenue,
            fcf_margin=args.fcf_margin,
            wacc=args.wacc,
            terminal_growth=args.terminal_growth,
            net_debt=args.net_debt,
            shares_outstanding=args.shares_outstanding,
            forecast_years=args.forecast_years,
        )
        print(f"Required revenue CAGR: {format_percent(required_growth)}")
        print(f"Model enterprise value: {format_currency(model_ev)}")
        return 0
    if args.command == "generate-report":
        path = _generate_report_impl(Path(args.input), Path(args.output))
        print(f"Wrote {path}")
        return 0
    if args.command == "launch-app":
        return _launch_app_impl()
    return 1


if __name__ == "__main__":
    if typer is None:
        raise SystemExit(_fallback_main())
    app()
