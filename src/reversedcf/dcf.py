"""Core discounted cash flow model."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DCFInputs:
    """Assumptions required to run a standard DCF valuation."""

    current_revenue: float
    revenue_cagr: float
    fcf_margin: float
    forecast_years: int
    wacc: float
    terminal_growth: float
    net_debt: float
    shares_outstanding: float

    def __post_init__(self) -> None:
        if self.current_revenue <= 0:
            raise ValueError("current_revenue must be positive.")
        if self.forecast_years <= 0:
            raise ValueError("forecast_years must be positive.")
        if self.shares_outstanding <= 0:
            raise ValueError("shares_outstanding must be positive.")
        if self.wacc <= self.terminal_growth:
            raise ValueError("WACC must be greater than terminal growth.")
        if self.wacc <= -1:
            raise ValueError("wacc must be greater than -100%.")
        if self.terminal_growth <= -1:
            raise ValueError("terminal_growth must be greater than -100%.")
        if self.fcf_margin <= -1:
            raise ValueError("fcf_margin must be greater than -100%.")
        if self.revenue_cagr <= -1:
            raise ValueError("revenue_cagr must be greater than -100%.")


@dataclass(frozen=True)
class DCFProjection:
    """Projected revenue, FCF, and present value by forecast year."""

    revenue: pd.Series
    free_cash_flow: pd.Series
    discounted_fcf: pd.Series
    terminal_value: float
    discounted_terminal_value: float


@dataclass(frozen=True)
class DCFValuation:
    """Enterprise and equity value outputs from a DCF run."""

    enterprise_value: float
    equity_value: float
    implied_share_price: float
    projection: DCFProjection
    inputs: DCFInputs


def project_revenue(
    current_revenue: float, revenue_cagr: float, forecast_years: int
) -> pd.Series:
    """Project revenue forward using a constant compound growth rate."""

    if current_revenue <= 0:
        raise ValueError("current_revenue must be positive.")
    if forecast_years <= 0:
        raise ValueError("forecast_years must be positive.")
    if revenue_cagr <= -1:
        raise ValueError("revenue_cagr must be greater than -100%.")

    years = range(1, forecast_years + 1)
    values = [current_revenue * (1 + revenue_cagr) ** year for year in years]
    return pd.Series(values, index=pd.Index(years, name="year"), name="revenue")


def project_fcf(revenue_series: pd.Series, fcf_margin: float) -> pd.Series:
    """Project free cash flow from revenue and a constant FCF margin."""

    if revenue_series.empty:
        raise ValueError("revenue_series must contain at least one forecast year.")
    if fcf_margin <= -1:
        raise ValueError("fcf_margin must be greater than -100%.")

    fcf = revenue_series * fcf_margin
    fcf.name = "free_cash_flow"
    return fcf


def discount_cash_flows(fcf_series: pd.Series, wacc: float) -> pd.Series:
    """Discount forecast free cash flows to present value."""

    if fcf_series.empty:
        raise ValueError("fcf_series must contain at least one forecast year.")
    if wacc <= -1:
        raise ValueError("wacc must be greater than -100%.")

    discounted = pd.Series(
        [cash_flow / (1 + wacc) ** year for year, cash_flow in fcf_series.items()],
        index=fcf_series.index,
        name="discounted_fcf",
    )
    return discounted


def terminal_value(final_fcf: float, wacc: float, terminal_growth: float) -> float:
    """Calculate Gordon Growth terminal value from final forecast-year FCF."""

    if wacc <= terminal_growth:
        raise ValueError("WACC must be greater than terminal growth.")
    if terminal_growth <= -1:
        raise ValueError("terminal_growth must be greater than -100%.")
    return final_fcf * (1 + terminal_growth) / (wacc - terminal_growth)


def _projection(inputs: DCFInputs) -> DCFProjection:
    revenue = project_revenue(
        inputs.current_revenue, inputs.revenue_cagr, inputs.forecast_years
    )
    fcf = project_fcf(revenue, inputs.fcf_margin)
    discounted_fcf = discount_cash_flows(fcf, inputs.wacc)
    tv = terminal_value(fcf.iloc[-1], inputs.wacc, inputs.terminal_growth)
    discounted_tv = tv / (1 + inputs.wacc) ** inputs.forecast_years
    return DCFProjection(
        revenue=revenue,
        free_cash_flow=fcf,
        discounted_fcf=discounted_fcf,
        terminal_value=tv,
        discounted_terminal_value=discounted_tv,
    )


def enterprise_value(inputs: DCFInputs) -> float:
    """Return enterprise value as PV of forecast FCF plus terminal value."""

    projection = _projection(inputs)
    return float(projection.discounted_fcf.sum() + projection.discounted_terminal_value)


def equity_value(inputs: DCFInputs) -> float:
    """Return equity value after subtracting net debt from enterprise value."""

    return enterprise_value(inputs) - inputs.net_debt


def implied_share_price(inputs: DCFInputs) -> float:
    """Return implied value per share."""

    return equity_value(inputs) / inputs.shares_outstanding


def run_dcf(inputs: DCFInputs) -> DCFValuation:
    """Run the complete DCF model and return valuation plus projections."""

    projection = _projection(inputs)
    ev = float(projection.discounted_fcf.sum() + projection.discounted_terminal_value)
    eq = ev - inputs.net_debt
    price = eq / inputs.shares_outstanding
    return DCFValuation(
        enterprise_value=ev,
        equity_value=eq,
        implied_share_price=price,
        projection=projection,
        inputs=inputs,
    )
