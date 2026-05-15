"""Run the bundled AAPL reverse DCF case study."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scripts.generate_report import build_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="data/sample_inputs/aapl.json",
        help="Manual fallback input path.",
    )
    parser.add_argument(
        "--output",
        default="reports/aapl_reverse_dcf_report.md",
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
        historical_growth=0.06,
        historical_margin=0.27,
    )
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
