import pytest

from reversedcf.dcf import DCFInputs
from reversedcf.financials import historical_revenue_cagr
from reversedcf.scenarios import run_scenario


def test_scenario_upside_downside_math():
    inputs = DCFInputs(
        current_revenue=100.0,
        revenue_cagr=0.0,
        fcf_margin=0.10,
        forecast_years=2,
        wacc=0.10,
        terminal_growth=0.0,
        net_debt=0.0,
        shares_outstanding=10.0,
    )

    result = run_scenario("Base", inputs, current_share_price=5.0)

    assert result.upside_downside == pytest.approx(result.implied_share_price / 5.0 - 1)


def test_historical_revenue_cagr_calculation():
    assert historical_revenue_cagr([100, 110, 121]) == pytest.approx(0.10)
