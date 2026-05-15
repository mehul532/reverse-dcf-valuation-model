"""Scenario analysis utilities."""

from __future__ import annotations

from dataclasses import dataclass, replace

from reversedcf.dcf import DCFInputs, run_dcf
from reversedcf.reverse import solve_required_revenue_cagr


@dataclass(frozen=True)
class Scenario:
    """Named DCF input set."""

    name: str
    inputs: DCFInputs


@dataclass(frozen=True)
class ScenarioResult:
    """Valuation output for a named scenario."""

    name: str
    enterprise_value: float
    equity_value: float
    implied_share_price: float
    upside_downside: float | None
    revenue_cagr: float
    fcf_margin: float
    wacc: float
    terminal_growth: float


def run_scenario(
    name: str, inputs: DCFInputs, current_share_price: float | None = None
) -> ScenarioResult:
    """Run a single scenario and optionally calculate upside/downside."""

    valuation = run_dcf(inputs)
    upside_downside = None
    if current_share_price is not None:
        if current_share_price <= 0:
            raise ValueError("current_share_price must be positive.")
        upside_downside = valuation.implied_share_price / current_share_price - 1

    return ScenarioResult(
        name=name,
        enterprise_value=valuation.enterprise_value,
        equity_value=valuation.equity_value,
        implied_share_price=valuation.implied_share_price,
        upside_downside=upside_downside,
        revenue_cagr=inputs.revenue_cagr,
        fcf_margin=inputs.fcf_margin,
        wacc=inputs.wacc,
        terminal_growth=inputs.terminal_growth,
    )


def run_scenarios(
    scenarios: list[Scenario], current_share_price: float | None = None
) -> list[ScenarioResult]:
    """Run multiple named scenarios."""

    return [
        run_scenario(scenario.name, scenario.inputs, current_share_price)
        for scenario in scenarios
    ]


def market_implied_scenario(
    target_enterprise_value: float, base_inputs: DCFInputs
) -> Scenario:
    """Build a scenario using the revenue CAGR implied by market enterprise value."""

    implied_growth = solve_required_revenue_cagr(target_enterprise_value, base_inputs)
    return Scenario(
        name="Market Implied",
        inputs=replace(base_inputs, revenue_cagr=implied_growth),
    )


def default_scenarios(
    base_inputs: DCFInputs, target_enterprise_value: float | None = None
) -> list[Scenario]:
    """Return a conservative set of Bear, Base, Bull, and optional market cases."""

    scenarios = [
        Scenario(
            "Bear",
            replace(
                base_inputs,
                revenue_cagr=max(base_inputs.revenue_cagr - 0.04, -0.95),
                fcf_margin=max(base_inputs.fcf_margin - 0.03, -0.95),
                wacc=base_inputs.wacc + 0.01,
                terminal_growth=base_inputs.terminal_growth - 0.005,
            ),
        ),
        Scenario("Base", base_inputs),
        Scenario(
            "Bull",
            replace(
                base_inputs,
                revenue_cagr=base_inputs.revenue_cagr + 0.04,
                fcf_margin=base_inputs.fcf_margin + 0.03,
                wacc=max(base_inputs.wacc - 0.01, base_inputs.terminal_growth + 0.001),
                terminal_growth=base_inputs.terminal_growth + 0.005,
            ),
        ),
    ]
    if target_enterprise_value is not None:
        scenarios.append(market_implied_scenario(target_enterprise_value, base_inputs))
    return scenarios
