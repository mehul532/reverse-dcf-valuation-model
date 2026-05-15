"""Streamlit dashboard for reverse DCF analysis."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

try:
    import streamlit as st
except ImportError:  # pragma: no cover - lets tests import without app extras
    st = None

from reversedcf.data import (
    CompanyValuationInputs,
    build_data_quality_statuses,
    company_inputs_to_dict,
    load_company_valuation_inputs,
)
from reversedcf.dcf import DCFInputs, run_dcf
from reversedcf.financials import build_historical_comparison_table
from reversedcf.metrics import format_currency, format_percent
from reversedcf.plotting import plot_scenario_prices
from reversedcf.reverse import (
    ReverseDCFError,
    solve_required_fcf_margin,
    solve_required_revenue_cagr,
    solve_required_terminal_growth,
    solve_required_wacc,
)
from reversedcf.scenarios import Scenario, market_implied_scenario, run_scenarios
from reversedcf.sensitivity import sensitivity_table_share_price


SAMPLE_AAPL_INPUTS = {
    "current_revenue": 391_000_000_000.0,
    "target_enterprise_value": 2_850_000_000_000.0,
    "net_debt": -50_000_000_000.0,
    "shares_outstanding": 15_263_000_000.0,
    "current_share_price": 190.0,
    "fcf_margin": 0.27,
}

INPUT_STATE_KEYS = {
    "current_revenue": "input_current_revenue",
    "target_enterprise_value": "input_target_enterprise_value",
    "net_debt": "input_net_debt",
    "shares_outstanding": "input_shares_outstanding",
    "current_share_price": "input_current_share_price",
    "fcf_margin": "input_fcf_margin",
}


if st is not None:

    @st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
    def _cached_load_company_data(query: str) -> CompanyValuationInputs:
        inputs = load_company_valuation_inputs(query)
        if not _has_usable_loaded_data(inputs):
            raise ValueError(
                "The lookup returned no usable valuation fields. Try a ticker or "
                "enter assumptions manually."
            )
        return inputs

else:

    def _cached_load_company_data(query: str) -> CompanyValuationInputs:
        return load_company_valuation_inputs(query)


def main() -> None:
    if st is None:
        raise RuntimeError(
            "Streamlit is not installed. Install app dependencies with "
            "`pip install -r requirements.txt`."
        )

    _init_session_state()

    st.set_page_config(page_title="Reverse DCF Valuation Model", layout="wide")
    st.title("Reverse DCF Valuation Model")
    st.caption(
        "Educational valuation tool only. Outputs depend heavily on assumptions "
        "and are not financial advice or investment recommendations."
    )

    with st.sidebar:
        st.header("Company Lookup")
        query = st.text_input(
            "Ticker or company name",
            placeholder="AAPL, MSFT, Apple, Microsoft",
            key="company_lookup_query",
        )

        load_clicked = st.button("Load company data", width="stretch")
        if load_clicked:
            if not query.strip():
                st.warning("Enter a ticker or company name before loading data.")
            else:
                _load_company_into_state(query)

        if st.button("Reset to sample AAPL inputs", width="stretch"):
            _reset_to_sample_inputs()
            st.info("Reset sidebar assumptions to the sample AAPL inputs.")

        if "loaded_company_inputs" in st.session_state:
            if st.button("Clear loaded data", width="stretch"):
                _clear_loaded_company()
                st.info("Cleared loaded company metadata. Manual inputs remain.")

        _show_load_messages()

        st.header("Editable Company Inputs")
        st.caption(
            "Loaded values are starting points from public data. Review and "
            "adjust every assumption before using the model."
        )
        current_revenue = st.number_input(
            "Current revenue",
            min_value=1.0,
            step=1_000_000_000.0,
            key=INPUT_STATE_KEYS["current_revenue"],
        )
        target_enterprise_value = st.number_input(
            "Market enterprise value",
            min_value=1.0,
            step=10_000_000_000.0,
            key=INPUT_STATE_KEYS["target_enterprise_value"],
        )
        net_debt = st.number_input(
            "Net debt (debt minus cash)",
            step=1_000_000_000.0,
            key=INPUT_STATE_KEYS["net_debt"],
        )
        shares_outstanding = st.number_input(
            "Shares outstanding",
            min_value=1.0,
            step=100_000_000.0,
            key=INPUT_STATE_KEYS["shares_outstanding"],
        )
        current_share_price = st.number_input(
            "Current share price",
            min_value=0.01,
            step=1.0,
            key=INPUT_STATE_KEYS["current_share_price"],
        )

        st.header("DCF Assumptions")
        revenue_cagr = st.slider("Revenue CAGR", -0.20, 0.50, 0.08, 0.005)
        fcf_margin = st.slider(
            "FCF margin",
            0.01,
            0.80,
            step=0.005,
            key=INPUT_STATE_KEYS["fcf_margin"],
        )
        wacc = st.slider("WACC", 0.03, 0.20, 0.08, 0.0025)
        terminal_growth = st.slider("Terminal growth", -0.02, 0.05, 0.025, 0.0025)
        forecast_years = st.slider("Forecast years", 1, 10, 5, 1)
        solve_for = st.selectbox(
            "Solve for",
            ["revenue CAGR", "FCF margin", "WACC", "terminal growth"],
        )

    try:
        inputs = DCFInputs(
            current_revenue=current_revenue,
            revenue_cagr=revenue_cagr,
            fcf_margin=fcf_margin,
            forecast_years=forecast_years,
            wacc=wacc,
            terminal_growth=terminal_growth,
            net_debt=net_debt,
            shares_outstanding=shares_outstanding,
        )
        valuation = run_dcf(inputs)
    except ValueError as exc:
        st.error(str(exc))
        return

    _show_loaded_company_box()

    solver = {
        "revenue CAGR": solve_required_revenue_cagr,
        "FCF margin": solve_required_fcf_margin,
        "WACC": solve_required_wacc,
        "terminal growth": solve_required_terminal_growth,
    }[solve_for]

    col1, col2, col3 = st.columns(3)
    col1.metric("DCF enterprise value", format_currency(valuation.enterprise_value))
    col2.metric("DCF equity value", format_currency(valuation.equity_value))
    col3.metric("DCF implied share price", format_currency(valuation.implied_share_price))

    solved_assumption: float | None = None
    solved_error: str | None = None
    st.subheader("Market-Implied Assumption")
    try:
        solved_assumption = solver(target_enterprise_value, inputs)
        st.metric(f"Required {solve_for}", format_percent(solved_assumption))
    except ReverseDCFError as exc:
        solved_error = str(exc)
        st.warning(solved_error)

    st.subheader("Sensitivity Table")
    wacc_values = [max(wacc - 0.01, terminal_growth + 0.001), wacc, wacc + 0.01]
    terminal_growth_values = [
        terminal_growth - 0.005,
        terminal_growth,
        terminal_growth + 0.005,
    ]
    table = sensitivity_table_share_price(inputs, wacc_values, terminal_growth_values)
    st.dataframe(table.style.format("${:,.2f}", na_rep="n/a"), width="stretch")

    st.subheader("Scenario Comparison")
    scenarios = [
        Scenario(
            "Bear",
            replace(
                inputs,
                revenue_cagr=max(revenue_cagr - 0.04, -0.95),
                fcf_margin=max(fcf_margin - 0.03, -0.95),
                wacc=wacc + 0.01,
                terminal_growth=terminal_growth - 0.005,
            ),
        ),
        Scenario("Base", inputs),
        Scenario(
            "Bull",
            replace(
                inputs,
                revenue_cagr=revenue_cagr + 0.04,
                fcf_margin=fcf_margin + 0.03,
                wacc=max(wacc - 0.01, terminal_growth + 0.001),
                terminal_growth=terminal_growth + 0.005,
            ),
        ),
    ]
    try:
        scenarios.append(market_implied_scenario(target_enterprise_value, inputs))
    except ReverseDCFError:
        pass

    scenario_results = run_scenarios(
        scenarios, current_share_price=current_share_price
    )
    st.pyplot(plot_scenario_prices(scenario_results))
    st.dataframe(
        [
            {
                "Scenario": result.name,
                "EV": result.enterprise_value,
                "Implied Price": result.implied_share_price,
                "Upside / Downside": result.upside_downside,
                "Revenue CAGR": result.revenue_cagr,
                "FCF Margin": result.fcf_margin,
                "WACC": result.wacc,
                "Terminal Growth": result.terminal_growth,
            }
            for result in scenario_results
        ],
        width="stretch",
    )

    historical_table = _show_historical_comparison(
        target_enterprise_value=target_enterprise_value,
        inputs=inputs,
        current_fcf_margin=fcf_margin,
    )
    _show_report_download(
        inputs=inputs,
        current_share_price=current_share_price,
        target_enterprise_value=target_enterprise_value,
        solve_for=solve_for,
        solved_assumption=solved_assumption,
        solved_error=solved_error,
        scenario_results=scenario_results,
        sensitivity_table=table,
        historical_table=historical_table,
    )


def _init_session_state() -> None:
    for field, key in INPUT_STATE_KEYS.items():
        if key not in st.session_state:
            st.session_state[key] = SAMPLE_AAPL_INPUTS[field]


def _load_company_into_state(query: str) -> None:
    try:
        loaded = _cached_load_company_data(query.strip())
    except Exception as exc:
        st.session_state["last_load_error"] = (
            f"Could not load company data for {query!r}: {exc}. "
            "Manual inputs remain editable."
        )
        st.session_state.pop("last_load_success", None)
        st.session_state.pop("last_load_missing", None)
        return

    _apply_loaded_values(loaded)
    st.session_state["loaded_company_inputs"] = company_inputs_to_dict(loaded)
    st.session_state["last_load_success"] = (
        f"Loaded {loaded.company_name} ({loaded.ticker})."
    )
    missing = _missing_key_fields(loaded)
    if missing:
        st.session_state["last_load_missing"] = (
            "Missing from live data: "
            + ", ".join(missing)
            + ". Review and fill these assumptions manually."
        )
    else:
        st.session_state.pop("last_load_missing", None)
    st.session_state.pop("last_load_error", None)


def _apply_loaded_values(loaded: CompanyValuationInputs) -> None:
    field_map = {
        "current_revenue": loaded.current_revenue,
        "target_enterprise_value": loaded.enterprise_value,
        "net_debt": loaded.net_debt,
        "shares_outstanding": loaded.shares_outstanding,
        "current_share_price": loaded.current_share_price,
    }
    for field, value in field_map.items():
        if value is None:
            continue
        if field in {
            "current_revenue",
            "target_enterprise_value",
            "shares_outstanding",
            "current_share_price",
        } and value <= 0:
            continue
        st.session_state[INPUT_STATE_KEYS[field]] = float(value)

    if loaded.fcf_margin is not None:
        st.session_state[INPUT_STATE_KEYS["fcf_margin"]] = min(
            max(float(loaded.fcf_margin), 0.01), 0.80
        )


def _reset_to_sample_inputs() -> None:
    for field, key in INPUT_STATE_KEYS.items():
        st.session_state[key] = SAMPLE_AAPL_INPUTS[field]
    _clear_loaded_company()


def _clear_loaded_company() -> None:
    for key in (
        "loaded_company_inputs",
        "last_load_success",
        "last_load_missing",
        "last_load_error",
    ):
        st.session_state.pop(key, None)


def _show_load_messages() -> None:
    if "last_load_success" in st.session_state:
        st.success(st.session_state["last_load_success"])
        st.info(
            "Loaded available data from yfinance; review and adjust assumptions "
            "before relying on the model."
        )
    if "last_load_missing" in st.session_state:
        st.warning(st.session_state["last_load_missing"])
    if "last_load_error" in st.session_state:
        st.warning(st.session_state["last_load_error"])


def _show_loaded_company_box() -> None:
    loaded = st.session_state.get("loaded_company_inputs")
    if not loaded:
        return

    st.subheader("Loaded Company Data")
    st.caption(
        "Public financial data can be incomplete or stale. Treat these values as "
        "editable assumptions, not guaranteed facts."
    )
    rows = [
        ("Company", loaded.get("company_name")),
        ("Ticker", loaded.get("ticker")),
        ("Source", loaded.get("source")),
        ("As of", loaded.get("as_of")),
        ("Current share price", _format_optional_currency(loaded.get("current_share_price"))),
        ("Market cap", _format_optional_currency(loaded.get("market_cap"))),
        ("Enterprise value", _format_optional_currency(loaded.get("enterprise_value"))),
        ("Net debt", _format_optional_currency(loaded.get("net_debt"))),
        ("Shares outstanding", _format_optional_number(loaded.get("shares_outstanding"))),
        ("Current revenue", _format_optional_currency(loaded.get("current_revenue"))),
        ("FCF margin", _format_optional_percent(loaded.get("fcf_margin"))),
    ]
    markdown = "\n".join(f"- **{label}:** {value or 'n/a'}" for label, value in rows)
    st.markdown(markdown)
    _show_data_quality_panel(loaded)


def _show_data_quality_panel(loaded: dict[str, Any]) -> None:
    st.subheader("Data Quality / Input Audit")
    st.warning(
        "Live financial data can be incomplete, stale, or estimated. Review every "
        "loaded value manually before using the valuation output."
    )
    quality = loaded.get("data_quality") or _fallback_data_quality(loaded)
    rows = [
        {
            "Input": _quality_label(field_name),
            "Status": details.get("status", "Missing / manual input needed"),
            "Note": details.get("note", ""),
        }
        for field_name, details in quality.items()
    ]
    st.dataframe(rows, width="stretch", hide_index=True)


def _show_historical_comparison(
    target_enterprise_value: float, inputs: DCFInputs, current_fcf_margin: float
) -> Any:
    st.subheader("Historical Comparison")
    loaded = st.session_state.get("loaded_company_inputs") or {}
    historical_revenues = loaded.get("historical_revenues") or ()
    historical_fcfs = loaded.get("historical_free_cash_flows") or ()
    historical_margins = loaded.get("historical_fcf_margins") or ()
    if not historical_revenues and not historical_fcfs and not historical_margins:
        st.info(
            "Historical revenue and free cash flow data is not available for this "
            "session. Load a company with available yfinance statements or compare "
            "history manually."
        )
        return None

    try:
        implied_growth = solve_required_revenue_cagr(target_enterprise_value, inputs)
    except ReverseDCFError:
        implied_growth = None

    table = build_historical_comparison_table(
        implied_revenue_cagr=implied_growth,
        current_fcf_margin=current_fcf_margin,
        historical_revenues=historical_revenues,
        historical_free_cash_flows=historical_fcfs,
        historical_fcf_margins=historical_margins,
    )
    if table["Historical"].isna().all():
        st.info(
            "Historical comparison data was loaded, but there were not enough "
            "valid observations to calculate growth or margin history."
        )
        return table

    st.caption(
        "Historical figures are context for the current assumptions; they are not "
        "forecasts or investment conclusions."
    )
    st.dataframe(
        table.style.format(
            {
                "Current / Implied": _format_optional_percent,
                "Historical": _format_optional_percent,
                "Spread": _format_optional_percent,
                "Historical Min": _format_optional_percent,
                "Historical Max": _format_optional_percent,
            },
            na_rep="n/a",
        ),
        width="stretch",
    )
    return table


def _show_report_download(
    *,
    inputs: DCFInputs,
    current_share_price: float,
    target_enterprise_value: float,
    solve_for: str,
    solved_assumption: float | None,
    solved_error: str | None,
    scenario_results: Any,
    sensitivity_table: Any,
    historical_table: Any,
) -> None:
    loaded = st.session_state.get("loaded_company_inputs") or {}
    company_name = loaded.get("company_name", "Manual Case")
    ticker = loaded.get("ticker", "MANUAL")
    data_quality = loaded.get("data_quality") or _fallback_data_quality(
        {
            "current_share_price": current_share_price,
            "enterprise_value": target_enterprise_value,
            "current_revenue": inputs.current_revenue,
            "fcf_margin": inputs.fcf_margin,
            "net_debt": inputs.net_debt,
            "shares_outstanding": inputs.shares_outstanding,
        }
    )
    report = build_app_markdown_report(
        company_name=company_name,
        ticker=ticker,
        inputs=inputs,
        current_share_price=current_share_price,
        target_enterprise_value=target_enterprise_value,
        solve_for=solve_for,
        solved_assumption=solved_assumption,
        solved_error=solved_error,
        scenario_results=scenario_results,
        sensitivity_table=sensitivity_table,
        data_quality=data_quality,
        historical_table=historical_table,
    )
    st.download_button(
        "Download valuation report",
        data=report,
        file_name=f"{str(ticker).lower()}_valuation_report.md",
        mime="text/markdown",
        width="stretch",
    )


def _missing_key_fields(inputs: CompanyValuationInputs) -> list[str]:
    fields = {
        "market enterprise value": inputs.enterprise_value,
        "current revenue": inputs.current_revenue,
        "shares outstanding": inputs.shares_outstanding,
        "net debt": inputs.net_debt,
        "current share price": inputs.current_share_price,
    }
    return [label for label, value in fields.items() if value is None]


def _has_usable_loaded_data(inputs: CompanyValuationInputs) -> bool:
    return any(
        value is not None
        for value in (
            inputs.current_share_price,
            inputs.market_cap,
            inputs.enterprise_value,
            inputs.current_revenue,
            inputs.shares_outstanding,
        )
    )


def _format_optional_currency(value: Any) -> str:
    return "n/a" if _is_missing(value) else format_currency(float(value))


def _format_optional_percent(value: Any) -> str:
    return "n/a" if _is_missing(value) else format_percent(float(value))


def _format_optional_number(value: Any) -> str:
    return "n/a" if _is_missing(value) else f"{float(value):,.0f}"


def _fallback_data_quality(data: dict[str, Any]) -> dict[str, dict[str, str]]:
    return build_data_quality_statuses(
        current_share_price=data.get("current_share_price"),
        market_cap=data.get("market_cap"),
        enterprise_value=data.get("enterprise_value")
        or data.get("target_enterprise_value"),
        current_revenue=data.get("current_revenue"),
        fcf_margin=data.get("fcf_margin"),
        net_debt=data.get("net_debt"),
        shares_outstanding=data.get("shares_outstanding"),
    )


def _quality_label(field_name: str) -> str:
    return {
        "current_share_price": "Current share price",
        "market_cap": "Market cap",
        "enterprise_value": "Enterprise value",
        "current_revenue": "Current revenue",
        "fcf_margin": "FCF margin",
        "net_debt": "Net debt",
        "shares_outstanding": "Shares outstanding",
    }.get(field_name, field_name.replace("_", " ").title())


def build_app_markdown_report(
    *,
    company_name: str,
    ticker: str,
    inputs: DCFInputs,
    current_share_price: float,
    target_enterprise_value: float,
    solve_for: str,
    solved_assumption: float | None,
    solved_error: str | None,
    scenario_results: Any,
    sensitivity_table: Any,
    data_quality: dict[str, dict[str, str]],
    historical_table: Any = None,
) -> str:
    """Build an in-memory markdown report from current app state."""

    lines = [
        f"# {company_name} ({ticker}) Reverse DCF App Report",
        "",
        "> Educational valuation model only. This report is not financial advice, "
        "does not predict stock prices, and should not be treated as an investment "
        "recommendation.",
        "",
        "## Current Valuation Inputs",
        "",
        "| Input | Value |",
        "| --- | ---: |",
        f"| Current share price | {format_currency(current_share_price)} |",
        f"| Market enterprise value | {format_currency(target_enterprise_value)} |",
        f"| Current revenue | {format_currency(inputs.current_revenue)} |",
        f"| Net debt | {format_currency(inputs.net_debt)} |",
        f"| Shares outstanding | {inputs.shares_outstanding:,.0f} |",
        "",
        "## DCF Assumptions",
        "",
        "| Assumption | Value |",
        "| --- | ---: |",
        f"| Revenue CAGR | {format_percent(inputs.revenue_cagr)} |",
        f"| FCF margin | {format_percent(inputs.fcf_margin)} |",
        f"| WACC | {format_percent(inputs.wacc)} |",
        f"| Terminal growth | {format_percent(inputs.terminal_growth)} |",
        f"| Forecast years | {inputs.forecast_years} |",
        "",
        "## Market-Implied Assumption",
        "",
    ]
    if solved_assumption is None:
        lines.append(f"- Required {solve_for}: not solved ({solved_error or 'n/a'})")
    else:
        lines.append(f"- Required {solve_for}: {format_percent(solved_assumption)}")

    lines.extend(
        [
            "",
            "## Scenario Comparison",
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

    lines.extend(["", "## Sensitivity Table", "", _markdown_from_table(sensitivity_table)])
    lines.extend(
        [
            "",
            "## Data Quality Notes",
            "",
            "| Input | Status | Note |",
            "| --- | --- | --- |",
        ]
    )
    for field_name, details in data_quality.items():
        lines.append(
            f"| {_quality_label(field_name)} | "
            f"{details.get('status', 'Missing / manual input needed')} | "
            f"{details.get('note', '')} |"
        )

    lines.extend(["", "## Historical Comparison", ""])
    if historical_table is None:
        lines.append("Historical comparison data was not available in this session.")
    else:
        lines.append(
            "Historical figures are context for the current assumptions; they are "
            "not forecasts or investment conclusions."
        )
        lines.append("")
        lines.append(_markdown_from_table(historical_table, percent_columns=True))

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Live financial data can be incomplete, stale, or estimated.",
            "- Reverse DCF outputs describe assumptions implied by selected inputs, not investment recommendations.",
            "- The output is only as good as the assumptions.",
            "- This report is for education and portfolio demonstration only, not financial advice.",
            "",
        ]
    )
    return "\n".join(lines)


def _markdown_from_table(table: Any, percent_columns: bool = False) -> str:
    if table is None:
        return "n/a"
    include_index = bool(getattr(table.index, "name", None))
    columns = [str(column) for column in table.columns]
    if include_index:
        columns = [str(table.index.name)] + columns
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for index, row in table.iterrows():
        cells = []
        if include_index:
            cells.append(str(index))
        for column in table.columns:
            value = row[column]
            if _is_missing(value):
                cells.append("n/a")
            elif percent_columns and column != "Metric":
                cells.append(_format_optional_percent(value))
            elif hasattr(value, "item"):
                try:
                    cells.append(f"{value.item():,.2f}")
                except Exception:
                    cells.append(str(value))
            elif isinstance(value, float):
                cells.append(f"{value:,.2f}")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    main()
