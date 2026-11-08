"""Research-only records preserve timing without inventing a declared model."""

from datetime import datetime, timezone
import json
import pytest
from test_strategy_case import NOW
from competition_tools.crypto_evidence import digest, seal, verify_seal

pytest_plugins = ["test_strategy_case"]


def at(hour, minute=0):
    return datetime(2026, 11, 9, hour, minute, tzinfo=timezone.utc)


@pytest.fixture
def observation_inputs(case, tmp_path):
    import exchange_calendars as xc
    from competition_tools.competition_review.research_cycle import propose

    proposal = tmp_path / "proposal"
    propose(
        tmp_path / "snapshot",
        proposal,
        core_conid="1",
        first_session="2026-11-09",
        material_deadline="2026-11-13T10:00:00Z",
        now=NOW,
    )
    cal = xc.get_calendar("XNYS", start="2025-01-01", end="2026-11-09").schedule.iloc[
        -200:
    ]
    values = [100] * 199 + [101]
    stamps = [int(r["open"].timestamp()) for _, r in cal.iterrows()]
    payload = dict(
        chart=dict(
            error=None,
            result=[
                dict(
                    meta=dict(
                        symbol="A",
                        currency="USD",
                        exchangeTimezoneName="America/New_York",
                    ),
                    timestamp=stamps,
                    indicators=dict(
                        quote=[dict(open=values, close=values)],
                        adjclose=[dict(adjclose=values)],
                    ),
                )
            ],
        )
    )
    source = tmp_path / "source"
    source.mkdir()
    price = source / "price.json"
    price.write_text(json.dumps(payload))
    receipt = dict(
        records=[
            dict(
                symbol="A",
                status="received",
                sha256=digest(price),
                requested_start="2025-01-01",
                requested_end_exclusive="2026-11-10",
                requested_at="2026-11-09T21:01:00Z",
                finished_at="2026-11-09T21:02:00Z",
            )
        ]
    )
    (source / "receipt.json").write_text(json.dumps(receipt))
    seal(source)
    return proposal, price


def record(inputs, out, now, price=True, session="2026-11-09"):
    from competition_tools.competition_review.candidate_observation import (
        record as capture,
    )

    proposal, path = inputs
    return capture(proposal, out, session, price_file=path if price else None, now=now)


@pytest.mark.parametrize(
    "now,price,status",
    [
        (at(20), True, "not_due"),
        (at(21, 31), True, "missed_deadline"),
        (at(21, 10), False, "blocked_missing_input"),
    ],
)
def test_timing_or_missing_inputs_never_create_signal(
    observation_inputs, tmp_path, now, price, status
):
    r = record(observation_inputs, tmp_path / "record", now, price)
    assert r["status"] == status and r["signal_diagnostic"] is None
    assert (
        r["actual_strategy_confirmed"] is False and r["execution_authorized"] is False
    )
    verify_seal(tmp_path / "record")


def test_valid_model_free_research_record_is_not_actual_strategy(
    observation_inputs, tmp_path
):
    r = record(observation_inputs, tmp_path / "record", at(21, 10))
    assert r["status"] == "recorded_diagnostic"
    assert r["signal_diagnostic"]["above_sma200"] is True
    assert r["signal_diagnostic"]["completed_sessions"] == 200
    assert r["source_semantics_independently_verified"] is False
    assert r["accepted_research"] is False
    assert not (tmp_path / "record" / "targets.json").exists()
    with pytest.raises(FileExistsError):
        record(observation_inputs, tmp_path / "record", at(21, 10))


@pytest.mark.parametrize(
    "mode",
    [
        "tamper",
        "old_capture",
        "future_capture",
        "wrong_symbol",
        "partial_history",
        "future_row",
        "future_row_outside_range",
        "empty_quote",
        "intraday_stamp",
    ],
)
def test_invalid_price_evidence_is_recorded_blocked(observation_inputs, tmp_path, mode):
    proposal, path = observation_inputs
    root = path.parent
    receipt = json.loads((root / "receipt.json").read_text())
    payload = json.loads(path.read_text())
    item = payload["chart"]["result"][0]
    if mode == "tamper":
        path.write_text("{}")
    else:
        if mode == "old_capture":
            receipt["records"][0]["requested_at"] = "2026-11-09T20:59:00Z"
        elif mode == "future_capture":
            receipt["records"][0]["finished_at"] = "2026-11-09T21:20:00Z"
        elif mode == "wrong_symbol":
            item["meta"]["symbol"] = "OTHER"
        elif mode == "partial_history":
            item["timestamp"] = item["timestamp"][1:]
            for key in ["open", "close"]:
                item["indicators"]["quote"][0][key] = item["indicators"]["quote"][0][
                    key
                ][1:]
            item["indicators"]["adjclose"][0]["adjclose"] = item["indicators"][
                "adjclose"
            ][0]["adjclose"][1:]
        elif mode == "empty_quote":
            item["indicators"]["quote"] = []
        elif mode == "future_row_outside_range":
            item["timestamp"].append(
                int(datetime(2026, 11, 10, 14, 30, tzinfo=timezone.utc).timestamp())
            )
            for key in ["open", "close"]:
                item["indicators"]["quote"][0][key].append(102)
            item["indicators"]["adjclose"][0]["adjclose"].append(102)
        elif mode == "future_row":
            item["timestamp"][-1] = int(
                datetime(2026, 11, 10, 14, 30, tzinfo=timezone.utc).timestamp()
            )
            receipt["records"][0]["requested_end_exclusive"] = "2026-11-11"
        elif mode == "intraday_stamp":
            item["timestamp"][-1] += 60
        path.write_text(json.dumps(payload))
        receipt["records"][0]["sha256"] = digest(path)
        (root / "receipt.json").write_text(json.dumps(receipt))
        (root / "seal.json").unlink()
        seal(root)
    r = record((proposal, path), tmp_path / "record", at(21, 10))
    assert r["status"] == "blocked_invalid_input" and r["signal_diagnostic"] is None
    assert r["price_evidence"] is None


def test_tampered_proposal_or_unknown_checkpoint_creates_no_output(
    observation_inputs, tmp_path
):
    with pytest.raises(ValueError):
        record(
            observation_inputs, tmp_path / "unknown", at(21, 10), session="2026-11-08"
        )
    assert not (tmp_path / "unknown").exists()
    (observation_inputs[0] / "proposal.json").write_text("{}")
    with pytest.raises(ValueError):
        record(observation_inputs, tmp_path / "bad", at(21, 10))
    assert not (tmp_path / "bad").exists()


def test_future_proposal_creation_rejected(observation_inputs, tmp_path):
    proposal, _ = observation_inputs
    p = json.loads((proposal / "proposal.json").read_text())
    p["created_at"] = "2026-11-09T21:20:00+00:00"
    (proposal / "proposal.json").write_text(json.dumps(p))
    (proposal / "seal.json").unlink()
    seal(proposal)
    with pytest.raises(ValueError, match="FUTURE_PROPOSAL_CREATION"):
        record(observation_inputs, tmp_path / "future-proposal", at(21, 10))
    assert not (tmp_path / "future-proposal").exists()
