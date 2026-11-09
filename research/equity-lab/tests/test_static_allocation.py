import copy
import json
import subprocess
import sys

import pytest

from equity_lab.backtest.static_allocation import replay, study


def panel():
    return [
        dict(date=d, open={"A": p}, close={"A": p})
        for d, p in [("2024-01-30", 100), ("2024-01-31", 120), ("2024-02-01", 120)]
    ]


def test_hold_units_and_initial_capital_drawdown():
    rows = panel()
    rows[1]["open"]["A"] = rows[1]["close"]["A"] = 80
    rows[2]["open"]["A"] = rows[2]["close"]["A"] = 80
    out = replay(rows, {"A": 0.5}, "hold", 0)
    assert out["return"] == pytest.approx(-0.1)
    assert out["drawdown"] == pytest.approx(-0.1)
    assert out["marks"][1]["weights"]["A"] == pytest.approx(4 / 9)
    assert len(out["trades"]) == 2


def test_constant_prices_entry_exit_cost_and_cash_funding():
    rows = panel()
    for row in rows:
        row["open"]["A"] = row["close"]["A"] = 100
    out = replay(rows, {"A": 1}, "monthly", 100)
    assert out["return"] == pytest.approx(0.99 / 1.01 - 1)
    assert out["cost"] == pytest.approx(1 - 0.99 / 1.01)
    assert all(m["cash"] >= 0 for m in out["marks"])
    assert out["drawdown"] == pytest.approx(out["return"])


def test_drift_uses_previous_close_not_current_open():
    rows = panel()
    rows[1]["open"]["A"] = 100
    rows[1]["close"]["A"] = 150
    rows[2]["open"]["A"] = rows[2]["close"]["A"] = 200
    out = replay(rows, {"A": 0.5}, "drift", 0)
    assert [t["date"] for t in out["trades"]] == [
        "2024-01-30",
        "2024-02-01",
        "2024-02-01",
    ]
    assert out["trades"][1]["reason"] == "prior_close_drift"
    assert out["marks"][1]["weights"]["A"] == pytest.approx(0.6)


def test_monthly_next_month_first_session():
    out = replay(panel(), {"A": 0.5}, "monthly", 0)
    assert [t["reason"] for t in out["trades"]] == [
        "entry",
        "month_boundary",
        "terminal",
    ]
    assert out["marks"][-1]["weights"]["A"] == pytest.approx(0.5)
    assert out["terminal_cash"] == pytest.approx(out["marks"][-1]["equity"])


@pytest.mark.parametrize(
    "mutation", ["duplicate", "unsorted", "missing", "badprice", "boolprice", "baddate"]
)
def test_invalid_panel(mutation):
    rows = panel()
    if mutation == "duplicate":
        rows[1]["date"] = rows[0]["date"]
    if mutation == "unsorted":
        rows.reverse()
    if mutation == "missing":
        rows[1]["close"] = {}
    if mutation == "badprice":
        rows[0]["open"]["A"] = float("nan")
    if mutation == "boolprice":
        rows[0]["open"]["A"] = True
    if mutation == "baddate":
        rows[0]["date"] = "2024-1-30"
    with pytest.raises(ValueError):
        replay(rows, {"A": 0.5}, "hold", 0)


@pytest.mark.parametrize(
    "target,policy,fee,threshold",
    [
        ({"A": True}, "hold", 0, 0.05),
        ({"B": 0.5}, "hold", 0, 0.05),
        ({"A": 1.1}, "hold", 0, 0.05),
        ({"A": 0.5}, "daily", 0, 0.05),
        ({"A": 0.5}, "hold", True, 0.05),
        ({"A": 0.5}, "drift", 0, 0),
    ],
)
def test_invalid_settings(target, policy, fee, threshold):
    with pytest.raises(ValueError):
        replay(panel(), target, policy, fee, threshold)


def protocol():
    return dict(
        schema="equity.static_allocation_protocol.v1",
        start="2024-01-30",
        end="2024-02-01",
        currency="USD",
        cash_yield=0,
        threshold=0.05,
        fees_bps=[0, 10, 25],
        policies=["hold", "monthly", "drift"],
        targets={"base": {"A": 0.5}},
    )


def test_complete_matrix_and_no_promotion():
    p = panel()
    original = copy.deepcopy(p)
    out = study(p, protocol())
    assert len(out["cases"]) == 9
    assert out["execution_authorized"] is False
    assert p == original
    assert out["cases"][0]["annual"][0]["year"] == 2024
    bad = protocol()
    bad["policies"] = ["hold", "hold"]
    with pytest.raises(ValueError):
        study(p, bad)


def test_cli_immutable_output(tmp_path):
    data = tmp_path / "input.json"
    data.write_text(json.dumps(panel()))
    config = tmp_path / "protocol.json"
    config.write_text(json.dumps(protocol()))
    output = tmp_path / "result.json"
    cmd = [
        sys.executable,
        "-m",
        "equity_lab.backtest.static_allocation",
        "--input",
        str(data),
        "--protocol",
        str(config),
        "--output",
        str(output),
    ]
    first = subprocess.run(cmd, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    original = output.read_bytes()
    assert len(json.loads(original)["input_sha256"]) == 64
    assert subprocess.run(cmd, capture_output=True).returncode != 0
    assert output.read_bytes() == original


def test_two_assets_cash_drift_and_continuous_annual_identity():
    rows = [
        dict(date=d, open={"A": a, "B": b}, close={"A": a, "B": b})
        for d, a, b in [
            ("2023-12-29", 100, 100),
            ("2024-01-02", 80, 120),
            ("2024-01-03", 80, 120),
        ]
    ]
    out = replay(rows, {"A": 0.5, "B": 0.25}, "monthly", 10)
    product = 1
    for year in out["annual"]:
        product *= 1 + year["return"]
    assert product == pytest.approx(1 + out["return"])
    assert sum(out["marks"][1]["weights"].values()) == pytest.approx(1)
    assert out["marks"][1]["open_weights"]["A"] == pytest.approx(0.5)
    assert out["marks"][1]["open_weights"]["B"] == pytest.approx(0.25)


def test_reserved_cash_name_rejected():
    rows = [
        {"date": r["date"], "open": {"_cash": 100}, "close": {"_cash": 100}}
        for r in panel()
    ]
    with pytest.raises(ValueError):
        replay(rows, {"_cash": 0.5}, "hold", 0)


def test_current_open_gap_alone_does_not_trigger_drift():
    rows = panel()
    for row in rows:
        row["open"]["A"] = row["close"]["A"] = 100
    rows[1]["open"]["A"] = 200
    out = replay(rows, {"A": 0.5}, "drift", 0)
    assert [t["reason"] for t in out["trades"]] == ["entry", "terminal"]
    assert out["return"] == pytest.approx(0)
