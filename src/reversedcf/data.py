"""Data access and manual input fallback helpers."""

from __future__ import annotations

import math
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
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


@dataclass(frozen=True)
class CompanyValuationInputs:
    """Best-effort live company inputs for valuation workflows."""

    ticker: str
    company_name: str
    current_share_price: float | None
    market_cap: float | None
    enterprise_value: float | None
    current_revenue: float | None
    fcf_margin: float | None
    net_debt: float | None
    shares_outstanding: float | None
    source: str
    as_of: str | None
    data_quality: dict[str, dict[str, str]] = field(default_factory=dict)
    historical_revenues: tuple[float, ...] = ()
    historical_free_cash_flows: tuple[float, ...] = ()
    historical_fcf_margins: tuple[float, ...] = ()


COMPANY_ALIAS_MAP: dict[str, str] = {
    "apple": "AAPL",
    "apple inc": "AAPL",
    "aapl": "AAPL",
    "microsoft": "MSFT",
    "microsoft corporation": "MSFT",
    "msft": "MSFT",
    "nvidia": "NVDA",
    "nvidia corporation": "NVDA",
    "nvda": "NVDA",
    "alphabet": "GOOGL",
    "alphabet inc": "GOOGL",
    "google": "GOOGL",
    "googl": "GOOGL",
    "amazon": "AMZN",
    "amazon com": "AMZN",
    "amazon.com": "AMZN",
    "amzn": "AMZN",
    "meta": "META",
    "meta platforms": "META",
    "facebook": "META",
    "tesla": "TSLA",
    "tsla": "TSLA",
    "netflix": "NFLX",
    "nflx": "NFLX",
    "berkshire": "BRK-B",
    "berkshire hathaway": "BRK-B",
    "brk-b": "BRK-B",
    "brk.b": "BRK-B",
    "jpmorgan": "JPM",
    "jpmorgan chase": "JPM",
    "jp morgan": "JPM",
    "jpm": "JPM",
    "visa": "V",
    "visa inc": "V",
    "v": "V",
    "mastercard": "MA",
    "mastercard incorporated": "MA",
    "ma": "MA",
}

_TICKER_RE = re.compile(r"^[A-Za-z]{1,6}([.-][A-Za-z]{1,2})?$")


def resolve_ticker(query: str) -> str:
    """Resolve a ticker or common company name to a ticker symbol."""

    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Enter a ticker or company name.")

    alias_key = _normalize_alias(cleaned)
    if alias_key in COMPANY_ALIAS_MAP:
        return COMPANY_ALIAS_MAP[alias_key]

    if _looks_like_ticker(cleaned):
        return cleaned.upper().replace(".", "-")

    searched = _search_ticker_yfinance(cleaned)
    if searched:
        return searched

    raise ValueError(f"Could not resolve {query!r} to a ticker.")


def load_company_valuation_inputs(ticker_or_name: str) -> CompanyValuationInputs:
    """Resolve and load best-effort valuation inputs for a company."""

    ticker = resolve_ticker(ticker_or_name)
    return load_company_valuation_inputs_from_yfinance(ticker)


def load_company_valuation_inputs_from_yfinance(ticker: str) -> CompanyValuationInputs:
    """Load company valuation inputs from yfinance defensively.

    yfinance statement labels and availability vary by company and over time, so
    unavailable fields are returned as ``None`` instead of raising.
    """

    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ImportError("Install yfinance to fetch live company data.") from exc

    resolved_ticker = ticker.strip().upper().replace(".", "-")
    stock = yf.Ticker(resolved_ticker)
    info = _safe_get_info(stock)
    fast_info = _safe_get_fast_info(stock)
    financials = _safe_statement(stock, "financials")
    cash_flow = _safe_statement(stock, "cashflow")
    balance_sheet = _safe_statement(stock, "balance_sheet")

    current_share_price = _first_available_float(
        info,
        "currentPrice",
        "regularMarketPrice",
        "previousClose",
        "regularMarketPreviousClose",
    )
    if current_share_price is None:
        current_share_price = _first_available_float(
            fast_info, "last_price", "lastPrice", "regular_market_previous_close"
        )

    market_cap = _first_available_float(info, "marketCap")
    if market_cap is None:
        market_cap = _first_available_float(fast_info, "market_cap", "marketCap")

    shares_outstanding = _first_available_float(info, "sharesOutstanding")
    shares_estimated = False
    if shares_outstanding is None and market_cap and current_share_price:
        shares_outstanding = market_cap / current_share_price
        shares_estimated = True

    current_revenue = _latest_statement_value(
        financials,
        [
            "Total Revenue",
            "Operating Revenue",
            "Revenue",
        ],
    )
    if current_revenue is None:
        current_revenue = _first_available_float(info, "totalRevenue", "revenue")

    operating_cash_flow = _latest_statement_value(
        cash_flow,
        [
            "Operating Cash Flow",
            "Total Cash From Operating Activities",
            "Cash Flow From Continuing Operating Activities",
        ],
    )
    capital_expenditures = _latest_statement_value(
        cash_flow,
        [
            "Capital Expenditure",
            "Capital Expenditures",
            "Capital Expenditure Reported",
        ],
    )
    free_cash_flow = _calculate_free_cash_flow(
        operating_cash_flow, capital_expenditures
    )
    if free_cash_flow is None:
        free_cash_flow = _first_available_float(info, "freeCashflow", "freeCashFlow")

    fcf_margin = None
    fcf_margin_estimated = False
    if free_cash_flow is not None and current_revenue and current_revenue != 0:
        fcf_margin = free_cash_flow / current_revenue
        fcf_margin_estimated = True

    total_debt = _latest_statement_value(
        balance_sheet,
        [
            "Total Debt",
            "TotalDebt",
            "Long Term Debt And Capital Lease Obligation",
            "Long Term Debt",
        ],
    )
    cash = _latest_statement_value(
        balance_sheet,
        [
            "Cash And Cash Equivalents",
            "Cash Cash Equivalents And Short Term Investments",
            "Cash And Short Term Investments",
            "Cash",
        ],
    )
    net_debt = calculate_net_debt(total_debt, cash)
    net_debt_estimated = net_debt is not None
    if net_debt is None:
        net_debt = _latest_statement_value(balance_sheet, ["Net Debt"])
        net_debt_estimated = False

    enterprise_value = _first_available_float(info, "enterpriseValue")
    enterprise_value_estimated = False
    if enterprise_value is None and market_cap is not None and net_debt is not None:
        enterprise_value = market_cap + net_debt
        enterprise_value_estimated = True

    company_name = (
        info.get("longName")
        or info.get("shortName")
        or info.get("displayName")
        or resolved_ticker
    )
    historical_revenues = _historical_statement_values(
        financials,
        [
            "Total Revenue",
            "Operating Revenue",
            "Revenue",
        ],
    )
    historical_operating_cash_flows = _historical_statement_values(
        cash_flow,
        [
            "Operating Cash Flow",
            "Total Cash From Operating Activities",
            "Cash Flow From Continuing Operating Activities",
        ],
    )
    historical_capex = _historical_statement_values(
        cash_flow,
        [
            "Capital Expenditure",
            "Capital Expenditures",
            "Capital Expenditure Reported",
        ],
    )
    historical_free_cash_flows = _historical_free_cash_flow_values(
        historical_operating_cash_flows, historical_capex
    )
    historical_fcf_margins = _historical_margin_values(
        historical_free_cash_flows, historical_revenues
    )

    data_quality = build_data_quality_statuses(
        current_share_price=current_share_price,
        market_cap=market_cap,
        enterprise_value=enterprise_value,
        current_revenue=current_revenue,
        fcf_margin=fcf_margin,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
        estimated_fields={
            "enterprise_value": "estimated as market cap + net debt"
            if enterprise_value_estimated
            else "",
            "fcf_margin": "estimated as free cash flow / revenue"
            if fcf_margin_estimated
            else "",
            "net_debt": "estimated as total debt minus cash"
            if net_debt_estimated
            else "",
            "shares_outstanding": "estimated from market cap / share price"
            if shares_estimated
            else "",
        },
    )

    return CompanyValuationInputs(
        ticker=resolved_ticker,
        company_name=str(company_name),
        current_share_price=current_share_price,
        market_cap=market_cap,
        enterprise_value=enterprise_value,
        current_revenue=current_revenue,
        fcf_margin=fcf_margin,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
        source="yfinance",
        as_of=datetime.now(timezone.utc).date().isoformat(),
        data_quality=data_quality,
        historical_revenues=tuple(historical_revenues),
        historical_free_cash_flows=tuple(historical_free_cash_flows),
        historical_fcf_margins=tuple(historical_fcf_margins),
    )


def calculate_net_debt(
    total_debt: float | None, cash: float | None
) -> float | None:
    """Calculate net debt as total debt minus cash."""

    debt_value = _to_float(total_debt)
    cash_value = _to_float(cash)
    if debt_value is None or cash_value is None:
        return None
    return debt_value - cash_value


def company_inputs_to_dict(inputs: CompanyValuationInputs) -> dict[str, Any]:
    """Convert company valuation inputs to a plain dictionary."""

    return asdict(inputs)


def build_data_quality_statuses(
    *,
    current_share_price: float | None,
    market_cap: float | None,
    enterprise_value: float | None,
    current_revenue: float | None,
    fcf_margin: float | None,
    net_debt: float | None,
    shares_outstanding: float | None,
    estimated_fields: dict[str, str] | None = None,
) -> dict[str, dict[str, str]]:
    """Build field-level data quality statuses for valuation inputs."""

    values = {
        "current_share_price": current_share_price,
        "market_cap": market_cap,
        "enterprise_value": enterprise_value,
        "current_revenue": current_revenue,
        "fcf_margin": fcf_margin,
        "net_debt": net_debt,
        "shares_outstanding": shares_outstanding,
    }
    estimated_fields = estimated_fields or {}
    statuses: dict[str, dict[str, str]] = {}
    for field_name, value in values.items():
        explanation = estimated_fields.get(field_name, "")
        if value is None:
            status = "Missing / manual input needed"
            note = "Not available from the loaded data."
        elif explanation:
            status = "Estimated"
            note = explanation
        else:
            status = "Loaded"
            note = "Loaded from source data."
        statuses[field_name] = {"status": status, "note": note}
    return statuses


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


def _normalize_alias(query: str) -> str:
    normalized = query.strip().lower().replace("&", "and")
    normalized = re.sub(r"[^a-z0-9.\-\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.rstrip(".")


def _looks_like_ticker(query: str) -> bool:
    return bool(_TICKER_RE.fullmatch(query.strip()))


def _search_ticker_yfinance(query: str) -> str | None:
    try:
        import yfinance as yf
    except ImportError:
        return None

    try:
        search_cls = getattr(yf, "Search", None)
        if search_cls is not None:
            search = search_cls(query, max_results=1)
            quotes = getattr(search, "quotes", None) or []
            if quotes:
                symbol = quotes[0].get("symbol")
                if symbol:
                    return str(symbol).upper().replace(".", "-")
    except Exception:
        return None

    return None


def _safe_get_info(stock: Any) -> dict[str, Any]:
    for getter_name in ("get_info",):
        getter = getattr(stock, getter_name, None)
        if getter is None:
            continue
        try:
            value = getter()
            if isinstance(value, dict):
                return value
        except Exception:
            pass

    try:
        value = getattr(stock, "info", {})
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _safe_get_fast_info(stock: Any) -> dict[str, Any]:
    try:
        value = getattr(stock, "fast_info", {})
        if isinstance(value, dict):
            return value
        if hasattr(value, "items"):
            return dict(value.items())
    except Exception:
        return {}
    return {}


def _safe_statement(stock: Any, attribute: str) -> pd.DataFrame:
    try:
        value = getattr(stock, attribute)
        if isinstance(value, pd.DataFrame):
            return value
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def _first_available_float(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in data:
            value = _to_float(data.get(key))
            if value is not None:
                return value
    return None


def _latest_statement_value(
    statement: pd.DataFrame, labels: list[str]
) -> float | None:
    if statement.empty:
        return None

    normalized_labels = {_normalize_statement_label(label) for label in labels}
    normalized_index = {
        _normalize_statement_label(str(index)): index for index in statement.index
    }

    for label in labels:
        if label in statement.index:
            value = _latest_non_null(statement.loc[label])
            if value is not None:
                return value

    for normalized in normalized_labels:
        if normalized in normalized_index:
            value = _latest_non_null(statement.loc[normalized_index[normalized]])
            if value is not None:
                return value

    return None


def _historical_statement_values(
    statement: pd.DataFrame, labels: list[str]
) -> list[float]:
    if statement.empty:
        return []

    normalized_labels = {_normalize_statement_label(label) for label in labels}
    normalized_index = {
        _normalize_statement_label(str(index)): index for index in statement.index
    }
    row = None
    for label in labels:
        if label in statement.index:
            row = statement.loc[label]
            break
    if row is None:
        for normalized in normalized_labels:
            if normalized in normalized_index:
                row = statement.loc[normalized_index[normalized]]
                break
    if row is None:
        return []
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    values = [_to_float(value) for value in row.tolist()]
    clean_values = [value for value in values if value is not None]
    return list(reversed(clean_values))


def _historical_free_cash_flow_values(
    operating_cash_flows: list[float], capital_expenditures: list[float]
) -> list[float]:
    pair_count = min(len(operating_cash_flows), len(capital_expenditures))
    if pair_count == 0:
        return []
    return [
        operating_cash_flows[-pair_count + index]
        - abs(capital_expenditures[-pair_count + index])
        for index in range(pair_count)
    ]


def _historical_margin_values(
    free_cash_flows: list[float], revenues: list[float]
) -> list[float]:
    pair_count = min(len(free_cash_flows), len(revenues))
    if pair_count == 0:
        return []
    margins: list[float] = []
    for index in range(pair_count):
        revenue = revenues[-pair_count + index]
        if revenue:
            margins.append(free_cash_flows[-pair_count + index] / revenue)
    return margins


def _normalize_statement_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]", "", label.lower())


def _latest_non_null(values: Any) -> float | None:
    if isinstance(values, pd.DataFrame):
        if values.empty:
            return None
        values = values.iloc[0]
    if isinstance(values, pd.Series):
        iterable = values.dropna().tolist()
    elif isinstance(values, (list, tuple)):
        iterable = values
    else:
        iterable = [values]

    for value in iterable:
        converted = _to_float(value)
        if converted is not None:
            return converted
    return None


def _calculate_free_cash_flow(
    operating_cash_flow: float | None, capital_expenditures: float | None
) -> float | None:
    ocf = _to_float(operating_cash_flow)
    capex = _to_float(capital_expenditures)
    if ocf is None or capex is None:
        return None
    return ocf - abs(capex)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "").strip()
        if not value:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number
