"""Streamlit dashboard for reverse DCF analysis."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

try:
    import streamlit as st
except ImportError:  # pragma: no cover - lets tests import without app extras
    st = None

from reversedcf.data import (
    CompanyValuationInputs,
    company_inputs_to_dict,
    load_company_valuation_inputs,
)
from reversedcf.dcf import DCFInputs, run_dcf
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

    st.subheader("Market-Implied Assumption")
    try:
        solved = solver(target_enterprise_value, inputs)
        st.metric(f"Required {solve_for}", format_percent(solved))
    except ReverseDCFError as exc:
        st.warning(str(exc))

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
    return "n/a" if value is None else format_currency(float(value))


def _format_optional_percent(value: Any) -> str:
    return "n/a" if value is None else format_percent(float(value))


def _format_optional_number(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):,.0f}"


if __name__ == "__main__":
    main()
