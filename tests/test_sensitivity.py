import pandas as pd

from reversedcf.dcf import DCFInputs
from reversedcf.sensitivity import sensitivity_table_share_price


def test_sensitivity_table_shape_and_labels():
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

    table = sensitivity_table_share_price(
        inputs,
        wacc_values=[0.08, 0.09],
        terminal_growth_values=[0.02, 0.03, 0.04],
    )

    assert table.shape == (2, 3)
    assert list(table.index) == ["8.0%", "9.0%"]
    assert list(table.columns) == ["2.0%", "3.0%", "4.0%"]


def test_sensitivity_table_marks_invalid_terminal_growth_as_nan():
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

    table = sensitivity_table_share_price(
        inputs,
        wacc_values=[0.04],
        terminal_growth_values=[0.03, 0.04],
    )

    assert table.loc["4.0%", "3.0%"] > 0
    assert pd.isna(table.loc["4.0%", "4.0%"])
