import pytest

from reversedcf.financials import (
    build_historical_comparison_table,
    historical_average_fcf_margin,
    historical_revenue_cagr_from_series,
)


def test_historical_revenue_cagr_from_series_sample_data():
    assert historical_revenue_cagr_from_series([100, 110, 121]) == pytest.approx(0.10)


def test_historical_average_fcf_margin_sample_data():
    stats = historical_average_fcf_margin(
        revenues=[100, 200, 300],
        free_cash_flows=[10, 30, 60],
    )

    assert stats["historical_average_fcf_margin"] == pytest.approx(0.15)
    assert stats["historical_min_fcf_margin"] == pytest.approx(0.10)
    assert stats["historical_max_fcf_margin"] == pytest.approx(0.20)


def test_build_historical_comparison_table():
    table = build_historical_comparison_table(
        implied_revenue_cagr=0.12,
        current_fcf_margin=0.25,
        historical_revenues=[100, 110, 121],
        historical_free_cash_flows=[20, 22, 24.2],
    )

    assert list(table["Metric"]) == ["Revenue CAGR", "FCF Margin"]
    assert table.loc[0, "Historical"] == pytest.approx(0.10)
    assert table.loc[1, "Historical"] == pytest.approx(0.20)
