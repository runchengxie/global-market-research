"""Common-ledger baseline comparisons retain timing and missing evidence."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from competition_tools.competition_review.baseline_decision import (
    points_for_arm,
    compare,
)
from competition_tools.competition_review.volatility_math import simulate


def rows():
    start = datetime(2024, 1, 25, 14, 30, tzinfo=timezone.utc)
    values = []
    for i in range(14):
        opening = start + timedelta(days=i)
        values.append(
            dict(
                date=opening.date().isoformat(),
                at=opening.isoformat(),
                close_at=(opening + timedelta(hours=6)).isoformat(),
                price=100 + i,
                close=100 + i,
            )
        )
    return values


def test_signal_uses_prior_completed_closes_and_future_edits_do_not_change_it():
    values = rows()
    before = points_for_arm(values, 3, 13, "sma_monthly", lookback=3, weight=0.5)
    assert before[0]["target"] == 0.5
    assert before[0]["signal_at"] < before[0]["at"]
    changed = [dict(r) for r in values]
    changed[10]["close"] = 999999
    after = points_for_arm(changed, 3, 13, "sma_monthly", lookback=3, weight=0.5)
    assert before[:7] == after[:7]


def test_equal_sma_means_cash_and_missing_history_never_means_cash():
    values = rows()
    for row in values:
        row["close"] = 100
    points = points_for_arm(values, 3, 13, "sma_monthly", lookback=3, weight=0.5)
    assert all(p["target"] == 0 for p in points)
    with pytest.raises(ValueError, match="INSUFFICIENT_BASELINE_HISTORY"):
        points_for_arm(values, 2, 13, "sma_monthly", lookback=3, weight=0.5)


def test_hold_does_not_rebalance_at_month_boundary_and_fee_formula_reconciles():
    points = points_for_arm(rows(), 3, 13, "partial_hold", lookback=3, weight=0.5)
    result = simulate(points, 25)
    fee = 25 / 10000
    ratio = points[-1]["price"] / points[0]["price"]
    expected = (0.5 + 0.5 * ratio * (1 - fee)) / (1 + 0.5 * fee)
    assert result["metrics"]["transaction_count"] == 2
    assert result["path"][-1]["nav"] == pytest.approx(expected)
    assert result["path"][0]["drawdown"] < 0
    assert any(r["exposure"] != pytest.approx(0.5) for r in result["path"][1:-1])


def test_cash_reference_has_no_trades_or_cost():
    result = simulate(points_for_arm(rows(), 3, 13, "cash", lookback=3, weight=0.5), 25)
    assert result["metrics"]["total_return"] == 0
    assert result["transactions"] == []


def test_missing_declared_model_stays_null_and_partial_year_is_not_a_win():
    results = [
        dict(
            episode="2024",
            full_year=True,
            arm=arm,
            fee_bps=10,
            status="completed",
            metrics=dict(total_return=ret, maximum_drawdown=-0.1),
        )
        for arm, ret in [("fixed_monthly", 0.1), ("sma_monthly", 0.11)]
    ]
    results += [
        dict(
            episode="2024",
            full_year=True,
            arm="declared_ranker",
            fee_bps=10,
            status="unavailable",
            metrics=None,
        )
    ]
    report = compare(results, ["2024", "2025"], [10], 1e-10, 0.0001)
    assert report["screen"] == "unknown_incomplete_comparisons"
    assert report["model_comparison"] == "blocked_missing_declared_model"
    assert report["adoption_authorized"] is False


@pytest.fixture
def integration_case(tmp_path, monkeypatch):
    import exchange_calendars as xc
    import json
    from competition_tools.competition_review import baseline_decision as module
    from competition_tools.crypto_evidence import digest, seal

    schedule = xc.get_calendar("XNYS", start="2023-01-01", end="2025-01-31").schedule
    data = [
        dict(
            date=d.date().isoformat(),
            event_at=row["open"].to_pydatetime(),
            adjusted_open=100 + i / 10,
            adjusted_close=100 + i / 10,
        )
        for i, (d, row) in enumerate(schedule.iterrows())
    ]
    source = tmp_path / "source"
    source.mkdir()
    payload = source / "usmv.json"
    payload.write_text("[]")
    (source / "receipt.json").write_text(
        json.dumps(
            dict(
                records=[
                    dict(
                        symbol="USMV",
                        status="received",
                        requested_at="2026-11-07T00:00:00Z",
                        finished_at="2026-11-07T01:00:00Z",
                    )
                ]
            )
        )
    )
    seal(source)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    manifest = inputs / "manifest.json"
    m = dict(sources=dict(usmv=dict(path=str(payload), sha256=digest(payload))))
    manifest.write_text(json.dumps(m))
    seal(inputs)
    protocol = tmp_path / "protocol"
    protocol.mkdir()
    p = dict(
        schema="competition.baseline_decision_protocol.v1",
        manifest_sha256=digest(manifest),
        source_revision="a" * 40,
        implementation_sha256=digest(Path(module.__file__)),
        symbol="USMV",
        currency="USD",
        frozen_at="2026-11-08T00:00:00Z",
        execution_authorized=False,
        history_previously_examined=True,
        parameter_optimization=False,
        start="2024-01-02",
        end="2025-01-31",
        sma_lookback=3,
        stock_weight=0.5,
        one_way_cost_bps=[0, 25],
        numerical_tolerance=1e-10,
        material_improvement=0.0001,
        required_share_numerator=2,
        required_share_denominator=3,
    )
    (protocol / "protocol.json").write_text(json.dumps(p))
    seal(protocol)
    # The existing sealed chart parser is tested separately; isolate annual orchestration here.
    monkeypatch.setattr(
        module, "_inputs", lambda path: (m, dict(usmv=data), dict(usmv={}))
    )
    return module, manifest, protocol, p


def test_orchestrator_keeps_every_arm_cost_and_partial_year(integration_case, tmp_path):
    from competition_tools.crypto_evidence import verify_seal

    module, manifest, protocol, _ = integration_case
    result = module.run(manifest, protocol, tmp_path / "result")
    assert result["requested_cases"] == 24
    assert result["completed_cases"] == 20
    assert result["unavailable_cases"] == 4
    assert [e["full_year"] for e in result["episodes"]] == [True, False]
    assert result["comparison"]["fee_screens"][0]["full_years"] == 1
    models = [c for c in result["cases"] if c["arm"] == "declared_ranker"]
    assert all(c["metrics"] is None and c["result"] is None for c in models)
    assert result["execution_authorized"] is False
    verify_seal(tmp_path / "result")
    with pytest.raises(FileExistsError):
        module.run(manifest, protocol, tmp_path / "result")


def test_protocol_rejects_execution_and_changed_input_bytes(integration_case, tmp_path):
    import json
    from competition_tools.crypto_evidence import seal

    module, manifest, protocol, values = integration_case
    values["execution_authorized"] = True
    (protocol / "protocol.json").write_text(json.dumps(values))
    (protocol / "seal.json").unlink()
    seal(protocol)
    with pytest.raises(ValueError, match="RETROSPECTIVE_USD_BASELINE_REQUIRED"):
        module.run(manifest, protocol, tmp_path / "result")
    assert not (tmp_path / "result").exists()
    values["execution_authorized"] = False
    (protocol / "protocol.json").write_text(json.dumps(values))
    (protocol / "seal.json").unlink()
    seal(protocol)
    manifest.write_text("{}")
    with pytest.raises(ValueError, match="BINDING_MISMATCH"):
        module.run(manifest, protocol, tmp_path / "changed")
