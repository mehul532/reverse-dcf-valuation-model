from reversedcf.data import (
    CompanyValuationInputs,
    calculate_net_debt,
    company_inputs_to_dict,
    load_manual_inputs,
    resolve_ticker,
)


def test_manual_input_loading_json(tmp_path):
    path = tmp_path / "inputs.json"
    path.write_text(
        """{
  "ticker": "XYZ",
  "company_name": "Example Co",
  "current_share_price": 10,
  "market_cap": 1000,
  "enterprise_value": 1100,
  "current_revenue": 200,
  "fcf_margin": 0.2,
  "net_debt": 100,
  "shares_outstanding": 100
}
""",
        encoding="utf-8",
    )

    inputs = load_manual_inputs(path)

    assert inputs.ticker == "XYZ"
    assert inputs.enterprise_value == 1100


def test_resolve_ticker_known_alias():
    assert resolve_ticker("Apple") == "AAPL"
    assert resolve_ticker("Apple Inc.") == "AAPL"


def test_resolve_ticker_direct_lowercase_symbol():
    assert resolve_ticker("msft") == "MSFT"


def test_calculate_net_debt_uses_debt_minus_cash():
    assert calculate_net_debt(total_debt=100.0, cash=30.0) == 70.0


def test_company_inputs_to_dict_converts_dataclass_cleanly():
    inputs = CompanyValuationInputs(
        ticker="AAPL",
        company_name="Apple Inc.",
        current_share_price=190.0,
        market_cap=2_900_000_000_000.0,
        enterprise_value=2_850_000_000_000.0,
        current_revenue=391_000_000_000.0,
        fcf_margin=0.27,
        net_debt=-50_000_000_000.0,
        shares_outstanding=15_263_000_000.0,
        source="unit-test",
        as_of="2026-05-15",
    )

    data = company_inputs_to_dict(inputs)

    assert data["ticker"] == "AAPL"
    assert data["net_debt"] == -50_000_000_000.0
    assert data["source"] == "unit-test"
