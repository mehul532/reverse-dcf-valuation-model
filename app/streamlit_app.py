"""Streamlit dashboard for reverse DCF analysis."""

from __future__ import annotations

from dataclasses import replace

try:
    import streamlit as st
except ImportError:  # pragma: no cover - lets tests import without app extras
    st = None

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


def main() -> None:
    if st is None:
        raise RuntimeError(
            "Streamlit is not installed. Install app dependencies with "
            "`pip install -r requirements.txt`."
        )

    st.set_page_config(page_title="Reverse DCF Valuation Model", layout="wide")
    st.title("Reverse DCF Valuation Model")
    st.caption(
        "Educational valuation tool only. Outputs depend heavily on assumptions "
        "and are not financial advice or investment recommendations."
    )

    with st.sidebar:
        st.header("Company Inputs")
        current_revenue = st.number_input(
            "Current revenue", min_value=1.0, value=391_000_000_000.0, step=1_000_000_000.0
        )
        target_enterprise_value = st.number_input(
            "Market enterprise value",
            min_value=1.0,
            value=2_850_000_000_000.0,
            step=10_000_000_000.0,
        )
        net_debt = st.number_input(
            "Net debt", value=-50_000_000_000.0, step=1_000_000_000.0
        )
        shares_outstanding = st.number_input(
            "Shares outstanding",
            min_value=1.0,
            value=15_263_000_000.0,
            step=100_000_000.0,
        )

        st.header("DCF Assumptions")
        revenue_cagr = st.slider("Revenue CAGR", -0.20, 0.50, 0.08, 0.005)
        fcf_margin = st.slider("FCF margin", 0.01, 0.80, 0.27, 0.005)
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
    terminal_growth_values = [terminal_growth - 0.005, terminal_growth, terminal_growth + 0.005]
    table = sensitivity_table_share_price(inputs, wacc_values, terminal_growth_values)
    st.dataframe(table.style.format("${:,.2f}"), use_container_width=True)

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

    current_share_price = (target_enterprise_value - net_debt) / shares_outstanding
    scenario_results = run_scenarios(scenarios, current_share_price=current_share_price)
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
        use_container_width=True,
    )


if __name__ == "__main__":
    main()
