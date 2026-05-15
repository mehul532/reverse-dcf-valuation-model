"""Data access and manual input fallback helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ManualInputs:
    """Company-level market and operating inputs for a reverse DCF case study."""

    ticker: str
    company_name: str
    current_share_price: float
    market_cap: float
    enterprise_value: float
    current_revenue: float
    fcf_margin: float
    net_debt: float
    shares_outstanding: float


def get_market_data_yfinance(ticker: str) -> dict[str, Any]:
    """Fetch market data from yfinance, returning a simple dictionary."""

    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ImportError("Install yfinance to fetch live market data.") from exc

    stock = yf.Ticker(ticker)
    info = stock.get_info()
    return {
        "ticker": ticker.upper(),
        "company_name": info.get("longName") or info.get("shortName") or ticker.upper(),
        "current_share_price": info.get("currentPrice")
        or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "shares_outstanding": info.get("sharesOutstanding"),
    }


def get_income_statement_yfinance(ticker: str) -> pd.DataFrame:
    """Fetch annual income statement data from yfinance."""

    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ImportError("Install yfinance to fetch income statements.") from exc

    return yf.Ticker(ticker).financials


def get_cash_flow_yfinance(ticker: str) -> pd.DataFrame:
    """Fetch annual cash flow statement data from yfinance."""

    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ImportError("Install yfinance to fetch cash flow statements.") from exc

    return yf.Ticker(ticker).cashflow


def load_manual_inputs(path: str | Path) -> ManualInputs:
    """Load manual inputs from JSON or CSV."""

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Manual input file not found: {file_path}")

    if file_path.suffix.lower() == ".json":
        data = json.loads(file_path.read_text(encoding="utf-8"))
    elif file_path.suffix.lower() == ".csv":
        frame = pd.read_csv(file_path)
        if frame.empty:
            raise ValueError("Manual input CSV is empty.")
        data = frame.iloc[0].to_dict()
    else:
        raise ValueError("Manual inputs must be a .json or .csv file.")

    required = {
        "ticker",
        "company_name",
        "current_share_price",
        "market_cap",
        "enterprise_value",
        "current_revenue",
        "fcf_margin",
        "net_debt",
        "shares_outstanding",
    }
    missing = sorted(required - data.keys())
    if missing:
        raise ValueError(f"Manual input file is missing fields: {', '.join(missing)}")

    return ManualInputs(
        ticker=str(data["ticker"]).upper(),
        company_name=str(data["company_name"]),
        current_share_price=float(data["current_share_price"]),
        market_cap=float(data["market_cap"]),
        enterprise_value=float(data["enterprise_value"]),
        current_revenue=float(data["current_revenue"]),
        fcf_margin=float(data["fcf_margin"]),
        net_debt=float(data["net_debt"]),
        shares_outstanding=float(data["shares_outstanding"]),
    )


def save_manual_inputs(inputs: ManualInputs | dict[str, Any], path: str | Path) -> None:
    """Save manual input data to JSON or CSV."""

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(inputs) if isinstance(inputs, ManualInputs) else dict(inputs)

    if file_path.suffix.lower() == ".json":
        file_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    elif file_path.suffix.lower() == ".csv":
        pd.DataFrame([data]).to_csv(file_path, index=False)
    else:
        raise ValueError("Manual inputs must be saved as .json or .csv.")
