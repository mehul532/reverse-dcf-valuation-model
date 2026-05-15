# Reverse DCF Valuation Model

Reverse DCF Valuation Model is an educational Python project for equity
research-style valuation analysis. It estimates what operating and valuation
assumptions are implied by a current market value.

This is not financial advice. The model does not predict stock prices, and it
should not be treated as an investment recommendation. Outputs depend heavily on
the selected assumptions.

## Motivation

A normal discounted cash flow model asks:

> What is this company worth under my assumptions?

A reverse DCF asks:

> What assumptions are already priced into the current market value?

That framing is useful because valuation debates often come down to whether the
market-implied revenue growth, free cash flow margin, discount rate, or terminal
value assumptions look plausible relative to a company's history and competitive
position.

## Features

- Standard DCF engine with dataclass-based inputs, projections, and valuation outputs.
- Reverse DCF solvers for revenue CAGR, FCF margin, WACC, and terminal growth.
- Sensitivity tables for share price, required growth, and required margin.
- Bear/base/bull/market-implied scenario analysis.
- Historical comparison helpers for growth and margin context.
- Manual JSON/CSV input fallback for reproducible case studies.
- Matplotlib report figures and stock pitch-style markdown reports.
- Typer CLI and Streamlit dashboard.
- Beginner notebooks for basic DCF, reverse solving, and case study workflow.

## Methodology

The model projects revenue over an explicit forecast period, applies a constant
free cash flow margin, discounts projected FCF at WACC, and estimates terminal
value with the Gordon Growth method:

```text
Enterprise Value = PV(forecast FCF) + PV(terminal value)
Equity Value = Enterprise Value - Net Debt
Implied Share Price = Equity Value / Shares Outstanding
```

Net debt is debt minus cash. Negative net debt represents net cash, which
increases equity value in the bridge from enterprise value to equity value.

Reverse DCF solvers use numerical root finding to identify the assumption that
makes modeled enterprise value approximately equal the selected market enterprise
value.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Run a bundled case study:

```bash
python scripts/run_aapl_case_study.py
python scripts/run_msft_case_study.py
```

Generate a report from a manual input file:

```bash
python scripts/generate_report.py \
  --input data/sample_inputs/aapl.json \
  --output reports/sample_report.md
```

## CLI Usage

```bash
python -m reversedcf.cli --help
python -m reversedcf.cli run-case-study --ticker AAPL
python -m reversedcf.cli solve-growth \
  --target-enterprise-value 2850000000000 \
  --current-revenue 391000000000 \
  --fcf-margin 0.27
python -m reversedcf.cli generate-report
```

## Streamlit Dashboard

```bash
streamlit run app/streamlit_app.py
```

The dashboard lets users enter revenue, market enterprise value, net debt,
shares outstanding, WACC, terminal growth, and FCF margin. It can solve for
market-implied revenue CAGR, FCF margin, WACC, or terminal growth, then show the
DCF valuation, sensitivity table, and scenario comparison chart.

## Sample Outputs

Generated artifacts are written to `reports/`:

- `reports/aapl_reverse_dcf_report.md`
- `reports/msft_reverse_dcf_report.md`
- `reports/sample_report.md`
- `reports/figures/*_revenue_forecast.png`
- `reports/figures/*_fcf_forecast.png`
- `reports/figures/*_sensitivity_heatmap.png`
- `reports/figures/*_scenario_prices.png`

## Data Inputs

Manual input files live in `data/sample_inputs/`. Monetary values should use a
consistent unit, such as actual dollars or millions of dollars. The bundled case
studies use actual dollar values.

Required fields:

- `ticker`
- `company_name`
- `current_share_price`
- `market_cap`
- `enterprise_value`
- `current_revenue`
- `fcf_margin`
- `net_debt`
- `shares_outstanding`

## Limitations

- The output is only as good as the assumptions.
- WACC and terminal value assumptions often drive a large share of DCF value.
- Constant growth and constant margin assumptions simplify real company behavior.
- Live financial data APIs can be incomplete or inconsistent; manual inputs are included for reproducibility.
- The model estimates assumptions implied by current valuation. It does not prove that a stock is undervalued or overvalued.

## References And Inspiration

- Discounted cash flow valuation and enterprise value frameworks used in equity research.
- Reverse DCF analysis popularized in public market valuation discussions.
- Standard corporate finance concepts: WACC, free cash flow, terminal value, and sensitivity analysis.
