from reversedcf.dcf import DCFInputs
from reversedcf.scenarios import Scenario, run_scenarios
from reversedcf.sensitivity import sensitivity_table_share_price

from app.streamlit_app import build_app_markdown_report


def test_build_app_markdown_report_from_app_style_inputs():
    inputs = DCFInputs(
        current_revenue=100.0,
        revenue_cagr=0.05,
        fcf_margin=0.20,
        forecast_years=5,
        wacc=0.09,
        terminal_growth=0.025,
        net_debt=10.0,
        shares_outstanding=10.0,
    )
    scenario_results = run_scenarios(
        [Scenario("Base", inputs)], current_share_price=10.0
    )
    sensitivity = sensitivity_table_share_price(
        inputs, wacc_values=[0.08, 0.09], terminal_growth_values=[0.02, 0.03]
    )
    data_quality = {
        "current_share_price": {"status": "Loaded", "note": "Loaded from source data."},
        "enterprise_value": {
            "status": "Estimated",
            "note": "estimated as market cap + net debt",
        },
    }

    report = build_app_markdown_report(
        company_name="Example Co",
        ticker="XYZ",
        inputs=inputs,
        current_share_price=10.0,
        target_enterprise_value=200.0,
        solve_for="revenue CAGR",
        solved_assumption=0.10,
        solved_error=None,
        scenario_results=scenario_results,
        sensitivity_table=sensitivity,
        data_quality=data_quality,
        historical_table=None,
    )

    assert "# Example Co (XYZ) Reverse DCF App Report" in report
    assert "Required revenue CAGR: 10.0%" in report
    assert "Data Quality Notes" in report
    assert "| WACC | 2.0% | 3.0% |" in report
    assert "estimated as market cap + net debt" in report
    assert "not financial advice" in report
