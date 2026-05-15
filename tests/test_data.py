from reversedcf.data import load_manual_inputs


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
