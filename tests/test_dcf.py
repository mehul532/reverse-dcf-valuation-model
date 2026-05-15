import pytest

from reversedcf.dcf import DCFInputs, enterprise_value, terminal_value


def test_enterprise_value_simple_known_example():
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

    expected = 10 / 1.1 + 10 / 1.1**2 + 100 / 1.1**2

    assert enterprise_value(inputs) == pytest.approx(expected)


def test_terminal_value_validation_when_wacc_not_above_terminal_growth():
    with pytest.raises(ValueError, match="WACC must be greater"):
        terminal_value(final_fcf=10.0, wacc=0.03, terminal_growth=0.03)
