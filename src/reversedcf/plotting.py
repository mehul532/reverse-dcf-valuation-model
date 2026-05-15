"""Matplotlib visualizations for DCF outputs."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Mapping, Sequence

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "reversedcf-matplotlib")
)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from reversedcf.dcf import DCFProjection
from reversedcf.metrics import format_currency, format_percent
from reversedcf.scenarios import ScenarioResult


def _save_or_return(fig: plt.Figure, output_path: str | Path | None) -> plt.Figure:
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=180, bbox_inches="tight")
    return fig


def plot_revenue_forecast(
    projection: DCFProjection, output_path: str | Path | None = None
) -> plt.Figure:
    """Plot forecast revenue by year."""

    fig, ax = plt.subplots(figsize=(8, 4.5))
    projection.revenue.plot(kind="bar", ax=ax, color="#2f80ed")
    ax.set_title("Revenue Forecast")
    ax.set_xlabel("Forecast Year")
    ax.set_ylabel("Revenue")
    ax.yaxis.set_major_formatter(lambda value, _: format_currency(value))
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    return _save_or_return(fig, output_path)


def plot_fcf_forecast(
    projection: DCFProjection, output_path: str | Path | None = None
) -> plt.Figure:
    """Plot forecast free cash flow by year."""

    fig, ax = plt.subplots(figsize=(8, 4.5))
    projection.free_cash_flow.plot(kind="bar", ax=ax, color="#20a67a")
    ax.set_title("Free Cash Flow Forecast")
    ax.set_xlabel("Forecast Year")
    ax.set_ylabel("Free Cash Flow")
    ax.yaxis.set_major_formatter(lambda value, _: format_currency(value))
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    return _save_or_return(fig, output_path)


def plot_sensitivity_heatmap(
    df: pd.DataFrame, title: str, output_path: str | Path | None = None
) -> plt.Figure:
    """Plot a sensitivity table as an annotated heatmap."""

    values = df.astype(float).to_numpy()
    fig, ax = plt.subplots(figsize=(max(6, df.shape[1] * 1.2), max(4, df.shape[0] * 0.8)))
    image = ax.imshow(values, cmap="RdYlGn", aspect="auto")
    ax.set_title(title)
    ax.set_xticks(np.arange(df.shape[1]), labels=df.columns)
    ax.set_yticks(np.arange(df.shape[0]), labels=df.index)
    ax.set_xlabel(df.columns.name or "")
    ax.set_ylabel(df.index.name or "")

    for row in range(df.shape[0]):
        for col in range(df.shape[1]):
            value = values[row, col]
            text = "n/a" if np.isnan(value) else _format_heatmap_value(value)
            ax.text(col, row, text, ha="center", va="center", fontsize=8)

    fig.colorbar(image, ax=ax, shrink=0.82)
    fig.tight_layout()
    return _save_or_return(fig, output_path)


def _format_heatmap_value(value: float) -> str:
    if abs(value) <= 1:
        return format_percent(value)
    return format_currency(value)


def plot_scenario_prices(
    results: Sequence[ScenarioResult], output_path: str | Path | None = None
) -> plt.Figure:
    """Plot implied share price across scenarios."""

    names = [result.name for result in results]
    prices = [result.implied_share_price for result in results]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(names, prices, color=["#d95f5f", "#4f80c0", "#3d9b6d", "#8b6fc7"][: len(names)])
    ax.set_title("Scenario Implied Share Prices")
    ax.set_ylabel("Implied Share Price")
    ax.yaxis.set_major_formatter(lambda value, _: format_currency(value))
    ax.grid(axis="y", alpha=0.25)
    for bar, price in zip(bars, prices):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            format_currency(price),
            ha="center",
            va="bottom",
            fontsize=8,
        )
    fig.tight_layout()
    return _save_or_return(fig, output_path)


def plot_implied_vs_historical(
    implied: float | Mapping[str, float],
    historical: float | Mapping[str, float],
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Compare implied assumptions with historical observations."""

    if isinstance(implied, Mapping) and isinstance(historical, Mapping):
        labels = list(implied.keys())
        implied_values = [implied[label] for label in labels]
        historical_values = [historical[label] for label in labels]
    else:
        labels = ["Assumption"]
        implied_values = [float(implied)]
        historical_values = [float(historical)]

    x = np.arange(len(labels))
    width = 0.36
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(x - width / 2, implied_values, width, label="Implied", color="#8b6fc7")
    ax.bar(x + width / 2, historical_values, width, label="Historical", color="#4f80c0")
    ax.set_title("Implied vs Historical Assumptions")
    ax.set_xticks(x, labels)
    ax.yaxis.set_major_formatter(lambda value, _: format_percent(value))
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    return _save_or_return(fig, output_path)
