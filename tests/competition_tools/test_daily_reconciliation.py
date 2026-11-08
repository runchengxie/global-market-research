"""Synthetic attribution only; no actual platform/account data."""

from collections import Counter
from copy import deepcopy
from decimal import Decimal
import json
import pytest
from test_strategy_case import NOW
from competition_tools.crypto_evidence import digest, seal, verify_seal

pytest_plugins = ["test_strategy_case", "test_competition_statements"]


def test_join_retains_missing_zero_and_unaligned_dates():
    from competition_tools.competition_review.daily_reconciliation import _join

    broker = [
        dict(
            report_date="2026-11-06",
            currency="USD",
            nav="100",
            stock_gross_value="50",
            stock_exposure_proxy=".5",
        ),
        dict(
            report_date="2026-11-05",
            currency="USD",
            nav="100",
            stock_gross_value="0",
            stock_exposure_proxy="0",
        ),
    ]
    platform = [
        dict(
            session_date="2026-11-06",
            position_rate="0",
            turnover_rate="0",
            flat_day=False,
            evidence="complete_declared_day",
        ),
        dict(
            session_date="2026-11-04",
            position_rate=None,
            turnover_rate=None,
            flat_day=None,
            evidence="unknown_or_partial",
        ),
    ]
    rows = _join(broker, Counter({"2026-11-06": 2}), platform)
    assert [r["date_label"] for r in rows] == ["2026-11-04", "2026-11-05", "2026-11-06"]
    assert rows[0]["status"] == "platform_calendar_day_without_broker_nav"
    assert rows[0]["broker_stock_exposure_proxy"] is None
    assert rows[1]["status"] == "broker_date_outside_supplied_elapsed_calendar"
    assert rows[1]["broker_stock_exposure_proxy"] == "0"
    assert rows[2]["platform_position_rate"] == "0"
    assert Decimal(rows[2]["numeric_proxy_minus_platform_position"]) == Decimal(".5")
    assert rows[2]["status"] == "same_label_requires_semantic_review"
    assert rows[2]["reported_execution_records"] == 2
    assert all(r["metric_equivalence"] == "unconfirmed" for r in rows)


def run(case, out, bundle=None, now=NOW):
    from competition_tools.competition_review.daily_reconciliation import run as capture

    return capture(
        case[1]["declaration_root"],
        case[1]["snapshot_root"],
        out,
        statement_bundle=bundle,
        now=now,
    )


def platform(case, bundle):
    path, raw = bundle
    raw = deepcopy(raw)
    raw.update(
        account_ref="paper",
        declaration_sha256=digest(
            __import__("pathlib").Path(case[1]["declaration_root"]) / "declaration.json"
        ),
    )
    raw["calendar"]["sessions"] = [
        dict(
            session_date="2026-11-06",
            opens_at="2026-11-06T14:30:00Z",
            closes_at="2026-11-06T21:00:00Z",
        )
    ]
    raw["days"][0].update(
        session_date="2026-11-06",
        position_rate=".5",
        covered_through="2026-11-06T21:00:00Z",
        available_at="2026-11-07T00:00:00Z",
    )
    path.write_text(json.dumps(raw))
    return path, raw


def test_missing_platform_stays_null_and_sealed(case, tmp_path):
    r = run(case, tmp_path / "result")
    assert r["platform_status"] == "missing"
    assert len(r["days"]) == 1
    assert r["days"][0]["platform_position_rate"] is None
    assert r["days"][0]["status"] == "missing_platform_evidence"
    assert (
        r["official_eligibility"] == "unverified" and r["execution_authorized"] is False
    )
    verify_seal(tmp_path / "result")
    with pytest.raises(FileExistsError):
        run(case, tmp_path / "result")


def test_equal_values_never_certify_matching_or_eligibility(case, bundle, tmp_path):
    p, _ = platform(case, bundle)
    r = run(case, tmp_path / "result", p)
    assert Decimal(r["days"][0]["numeric_proxy_minus_platform_position"]) == 0
    assert r["days"][0]["status"] == "same_label_requires_semantic_review"
    assert r["official_eligibility"] == "unverified"


@pytest.mark.parametrize(
    "mode", ["account", "currency", "declaration", "source", "future"]
)
def test_platform_mismatch_or_unavailable_source_creates_no_output(
    case, bundle, tmp_path, mode
):
    path, raw = platform(case, bundle)
    if mode == "account":
        raw["account_ref"] = "other"
    elif mode == "currency":
        raw["base_currency"] = "SGD"
    elif mode == "declaration":
        raw["declaration_sha256"] = "a" * 64
    elif mode == "source":
        raw["sources"][0]["sha256"] = "a" * 64
    elif mode == "future":
        raw["days"][0]["available_at"] = "2026-11-10T00:00:00Z"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        run(case, tmp_path / "bad", path)
    assert not (tmp_path / "bad").exists()


def test_tampered_derived_ledger_cannot_be_trusted(case, tmp_path):
    from pathlib import Path

    root = Path(case[1]["snapshot_root"])
    (root / "seal.json").unlink()
    (root / "ledger.json").write_text("{}")
    seal(root)
    with pytest.raises(ValueError, match="LEDGER_REPRODUCTION_MISMATCH"):
        run(case, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_duplicate_execution_ids_are_counted_once(case, tmp_path):
    from pathlib import Path

    root = Path(case[1]["snapshot_root"])
    row = '<Trade accountId="SYNTH" levelOfDetail="EXECUTION" tradeID="x" tradeDate="20261106" transactionType="ExchTrade" quantity="1" buySell="BUY" conid="1" symbol="A" assetCategory="STK" currency="USD" ibOrderID="o"/>'
    raw = (
        (root / "report.xml")
        .read_text()
        .replace(
            "</FlexStatement>", "<Trades>" + row + row + "</Trades></FlexStatement>"
        )
    )
    (root / "report.xml").write_text(raw)
    from competition_tools.competition_review.flex_reconciliation import (
        reconcile_snapshot,
    )

    (root / "snapshot.json").write_text(
        json.dumps(
            reconcile_snapshot(
                raw.encode(),
                expected_account="SYNTH",
                base_currency="USD",
                account_ref="paper",
            )
        )
    )
    receipt = json.loads((root / "receipt.json").read_text())
    receipt["report_sha256"] = digest(root / "report.xml")
    (root / "receipt.json").write_text(json.dumps(receipt))
    (root / "seal.json").unlink()
    seal(root)
    r = run(case, tmp_path / "result")
    assert r["days"][0]["reported_execution_records"] == 1
    assert r["broker_ledger"]["executions"]["duplicate_records"] == 1


def test_future_execution_date_in_sealed_report_is_rejected(case, tmp_path):
    from pathlib import Path
    from competition_tools.competition_review.flex_reconciliation import (
        reconcile_snapshot,
    )

    root = Path(case[1]["snapshot_root"])
    row = '<Trades><Trade accountId="SYNTH" levelOfDetail="EXECUTION" tradeID="future" tradeDate="20261109" transactionType="ExchTrade" quantity="1" buySell="BUY" conid="1" symbol="A" assetCategory="STK" currency="USD"/></Trades>'
    raw = (
        (root / "report.xml")
        .read_text()
        .replace('toDate="20261106"', 'toDate="20261109"')
        .replace("</FlexStatement>", row + "</FlexStatement>")
    )
    (root / "report.xml").write_text(raw)
    (root / "snapshot.json").write_text(
        json.dumps(
            reconcile_snapshot(
                raw.encode(),
                expected_account="SYNTH",
                base_currency="USD",
                account_ref="paper",
            )
        )
    )
    receipt = json.loads((root / "receipt.json").read_text())
    receipt["report_sha256"] = digest(root / "report.xml")
    (root / "receipt.json").write_text(json.dumps(receipt))
    (root / "seal.json").unlink()
    seal(root)
    with pytest.raises(ValueError):  # Existing snapshot/period gates reject this first.
        run(case, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_execution_after_receipt_but_before_run_time_rejected(case, tmp_path):
    from pathlib import Path
    from competition_tools.competition_review.flex_reconciliation import (
        reconcile_snapshot,
    )

    root = Path(case[1]["snapshot_root"])
    row = '<Trades><Trade accountId="SYNTH" levelOfDetail="EXECUTION" tradeID="late" tradeDate="20261108" transactionType="ExchTrade" quantity="1" buySell="BUY" conid="1" symbol="A" assetCategory="STK" currency="USD"/></Trades>'
    raw = (
        (root / "report.xml")
        .read_text()
        .replace('toDate="20261106"', 'toDate="20261108"', 1)
        .replace("</FlexStatement>", row + "</FlexStatement>")
    )
    (root / "report.xml").write_text(raw)
    snapshot = reconcile_snapshot(
        raw.encode(), expected_account="SYNTH", base_currency="USD", account_ref="paper"
    )
    assert snapshot["status"] == "reconciled_stock_cash"
    (root / "snapshot.json").write_text(json.dumps(snapshot))
    receipt = json.loads((root / "receipt.json").read_text())
    receipt["report_sha256"] = digest(root / "report.xml")
    (root / "receipt.json").write_text(json.dumps(receipt))
    (root / "seal.json").unlink()
    seal(root)
    with pytest.raises(ValueError, match="BROKER_DATE_AFTER_RECEIPT"):
        run(case, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
