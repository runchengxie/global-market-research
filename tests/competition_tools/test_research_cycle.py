"""Specific hypotheses and forward-only research calendar, not account policy."""

import pytest
from test_strategy_case import NOW
from competition_tools.crypto_evidence import verify_seal

pytest_plugins = ["test_strategy_case"]
DEADLINE = "2026-11-13T10:00:00Z"


def propose(root, out, **kwargs):
    from competition_tools.competition_review.research_cycle import propose as make

    args = dict(
        core_conid="1", first_session="2026-11-09", material_deadline=DEADLINE, now=NOW
    )
    args.update(kwargs)
    return make(root, out, **args)


def test_specific_arms_calendar_and_unknown_signal_stay_distinct(case, tmp_path):
    result = propose(tmp_path / "snapshot", tmp_path / "proposal")
    arms = result["candidates"]
    assert [a["id"] for a in arms] == [
        "observed_reference",
        "fixed_half",
        "initial_trend_half",
    ]
    assert arms[0]["initial_reference_stock_weights"] == {"1": "0.5"}
    assert arms[1]["initial_reference_stock_weights"] == {"1": "0.5"}
    assert arms[2]["initial_reference_stock_weights"] is None
    assert arms[2]["signal_status"] == "blocked_history_unverified"
    assert arms[2]["rule"]["observations"] == 200
    assert result["fees"]["one_way_bps"] == ["0", "10", "25"]
    schedule = result["schedule"]
    assert schedule["initial_signal_deadline"] == "2026-11-09T21:30:00+00:00"
    assert schedule["entry"] == "2026-11-10T14:30:00+00:00"
    assert len(schedule["daily_checks"]) == 20
    assert all(x["session_date"] != "2026-11-26" for x in schedule["daily_checks"])
    halfday = next(
        x for x in schedule["daily_checks"] if x["session_date"] == "2026-11-27"
    )
    assert halfday["review_deadline"] == "2026-11-27T18:30:00+00:00"
    assert schedule["exit"] == "2026-12-09T14:30:00+00:00"
    assert result["status"] == "frozen_research_proposal_awaiting_inputs"
    assert (
        result["actual_policy_confirmed"] is False
        and result["execution_authorized"] is False
    )
    verify_seal(tmp_path / "proposal")
    assert not (tmp_path / "proposal" / "targets.json").exists()
    with pytest.raises(FileExistsError):
        propose(tmp_path / "snapshot", tmp_path / "proposal")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"core_conid": "2"},
        {"core_conid": True},
        {"first_session": "2026-11-06"},
        {"first_session": "2027-01-25"},
        {"material_deadline": "2026-11-07T10:00:00Z"},
        {"material_deadline": "2026-11-09T20:00:00Z"},
        {"material_deadline": "2026-12-10T10:00:00Z"},
        {"material_deadline": "2026-11-13T10:00:00"},
    ],
)
def test_bad_identity_dates_or_cutoff_create_no_output(case, tmp_path, kwargs):
    with pytest.raises(ValueError):
        propose(tmp_path / "snapshot", tmp_path / "bad", **kwargs)
    assert not (tmp_path / "bad").exists()


def test_tampered_snapshot_cannot_become_research_reference(case, tmp_path):
    (tmp_path / "snapshot" / "snapshot.json").write_text("{}")
    with pytest.raises(ValueError):
        propose(tmp_path / "snapshot", tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_leveraged_reference_is_not_silently_rescaled(case, tmp_path):
    from test_strategy_case import RAW, write
    from competition_tools.competition_review.flex_reconciliation import (
        reconcile_snapshot,
    )
    from competition_tools.crypto_evidence import digest, read_json, seal

    root = tmp_path / "snapshot"
    raw = (
        RAW.replace(b'position="50"', b'position="150"')
        .replace(b'positionValue="50"', b'positionValue="150"')
        .replace(b'stock="50" stockLong="50"', b'stock="150" stockLong="150"')
        .replace(b'cash="50"', b'cash="-50"')
        .replace(b'endingCash="50"', b'endingCash="-50"')
    )
    (root / "report.xml").write_bytes(raw)
    write(
        root / "snapshot.json",
        reconcile_snapshot(
            raw, expected_account="SYNTH", base_currency="USD", account_ref="paper"
        ),
    )
    receipt = read_json(root / "receipt.json")
    receipt["report_sha256"] = digest(root / "report.xml")
    write(root / "receipt.json", receipt)
    (root / "seal.json").unlink()
    seal(root)
    with pytest.raises(ValueError, match="UNLEVERED"):
        propose(root, tmp_path / "bad")


def test_cycle_cannot_start_before_contest_envelope():
    from datetime import datetime, timezone
    from competition_tools.competition_review.research_cycle import _schedule

    with pytest.raises(ValueError):
        _schedule(
            "2026-10-21",
            datetime(2026, 10, 23, 10, tzinfo=timezone.utc),
            datetime(2026, 10, 20, tzinfo=timezone.utc),
        )
