from dataclasses import replace

import pytest

from reversedcf.dcf import DCFInputs, enterprise_value
from reversedcf.reverse import (
    solve_required_fcf_margin,
    solve_required_revenue_cagr,
)


def test_solver_recovers_known_revenue_cagr():
    base_inputs = DCFInputs(
        current_revenue=100.0,
        revenue_cagr=0.05,
        fcf_margin=0.20,
        forecast_years=5,
        wacc=0.09,
        terminal_growth=0.025,
        net_debt=0.0,
        shares_outstanding=10.0,
    )
    target_inputs = replace(base_inputs, revenue_cagr=0.12)
    target_ev = enterprise_value(target_inputs)

    solved = solve_required_revenue_cagr(target_ev, base_inputs)

    assert solved == pytest.approx(0.12, abs=1e-8)


def test_solver_recovers_known_fcf_margin():
    base_inputs = DCFInputs(
        current_revenue=100.0,
        revenue_cagr=0.08,
        fcf_margin=0.15,
        forecast_years=5,
        wacc=0.09,
        terminal_growth=0.025,
        net_debt=0.0,
        shares_outstanding=10.0,
    )
    target_inputs = replace(base_inputs, fcf_margin=0.27)
    target_ev = enterprise_value(target_inputs)

    solved = solve_required_fcf_margin(target_ev, base_inputs)

    assert solved == pytest.approx(0.27, abs=1e-8)
