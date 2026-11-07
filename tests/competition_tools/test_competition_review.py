from datetime import datetime, timezone
from decimal import Decimal
import json
import pytest
from competition_tools.competition_review.participation import (
    daily_rows,
    summarize_days,
    future_bounds,
)
from competition_tools.competition_review.evidence import (
    load_observations,
    calendar_scenario,
)

NOW = datetime(2026, 11, 7, 15, tzinfo=timezone.utc)


def test_missing_is_unknown_and_complete_intraday_is_not_flat():
    rows = daily_rows(
        ["2026-10-26", "2026-10-27"],
        [
            dict(
                session_date="2026-10-26",
                complete_day=True,
                position_rate="0",
                turnover_rate="1",
                had_any_position=True,
                had_any_trade=True,
            )
        ],
    )
    assert rows[0]["flat_day"] is False and rows[1]["position_rate"] is None
    assert summarize_days(rows)["eligibility_under_inputs"] == "unknown"
    result = summarize_days(rows[:1])
    assert (
        result["path_b_under_inputs"] == "met"
        and result["eligibility_under_inputs"] == "met"
    )
    assert result["official_eligibility"] == "unverified"


def test_position_route_and_threshold_or():
    days = [
        dict(
            session_date=f"2026-10-{26 + i}",
            complete_day=True,
            position_rate=".5",
            turnover_rate="0",
            had_any_position=True,
            had_any_trade=False,
        )
        for i in range(3)
    ]
    r = summarize_days(daily_rows([d["session_date"] for d in days], days))
    assert r["path_a_under_inputs"] == "met" and r["path_b_under_inputs"] == "not_met"
    days[0]["position_rate"] = ".4"
    assert (
        summarize_days(daily_rows([d["session_date"] for d in days], days))[
            "eligibility_under_inputs"
        ]
        == "not_met"
    )
    with pytest.raises(ValueError):
        daily_rows(["2026-10-26"], days + days)
    days[0]["position_rate"] = "NaN"
    with pytest.raises(ValueError):
        daily_rows(["2026-10-26"], days)


def test_future_bounds_do_not_replace_missing_history():
    r = future_bounds(Decimal("0"), 10, 0, 60)
    assert Decimal(r["maximum_required_future_mean"]) == Decimal(35) / 60
    assert (
        future_bounds(Decimal("0"), 0, 10, 60)["minimum_required_future_mean"]
        != r["maximum_required_future_mean"]
    )
    assert future_bounds(Decimal("0"), 2, 0, 0)["status"] == "no_future_sessions"


def test_deduplicate_observations_but_reject_conflicting_time(tmp_path):
    root = tmp_path / "observations"
    (root / "a").mkdir(parents=True)
    (root / "b").mkdir()
    x = dict(
        observed_at="2026-10-30T02:00:00Z",
        net_liquidation_sgd="100",
        gross_position_sgd="55",
        stock_positions=[dict(symbol="AAA", quantity="1", currency="USD")],
    )
    for n in ["a", "b"]:
        (root / n / "snapshot.json").write_text(json.dumps(x))
    result = load_observations(root, NOW)
    assert len(result["observations"]) == 1 and result["duplicate_files"] == 1
    x["gross_position_sgd"] = "60"
    (root / "b/snapshot.json").write_text(json.dumps(x))
    result = load_observations(root, NOW)
    assert not result["observations"] and result["conflicts"]


def test_aware_time_and_calendar_boundary(tmp_path):
    root = tmp_path / "observations"
    (root / "a").mkdir(parents=True)
    (root / "a/snapshot.json").write_text(
        json.dumps(
            dict(
                observed_at="2026-10-30T02:00:00",
                net_liquidation_sgd="100",
                gross_position_sgd="55",
                stock_positions=[],
            )
        )
    )
    assert load_observations(root, NOW)["invalid_files"]
    pytest.importorskip("exchange_calendars")
    x = calendar_scenario("XNYS", NOW)
    assert len(x["elapsed_sessions"]) == 10
    assert "2027-01-27" not in x["all_sessions"]
    y = calendar_scenario("XTKS", NOW)
    assert "2026-11-03" not in y["elapsed_sessions"]


def test_already_excess_flat_days_cannot_be_hidden_by_unknowns():
    rows = [
        dict(position_rate=None, turnover_rate=None, flat_day=True) for _ in range(11)
    ] + [dict(position_rate=None, turnover_rate=None, flat_day=None)]
    assert summarize_days(rows)["path_a_under_inputs"] == "not_met"


def test_daily_review_blocks_missing_stale_and_future():
    from competition_tools.competition_review.decision import review_decision

    policy = {"status": "draft"}
    result = review_decision(policy, {}, NOW)
    assert result["status"] == "blocked"
    assert result["execution_authorized"] is False


def test_complete_review_requires_causal_sources_and_checks_drift():
    from competition_tools.competition_review.decision import review_decision

    policy = dict(
        status="confirmed",
        benchmark="SYNTHETIC",
        declaration_sha256="b" * 64,
        model_sha256="a" * 64,
        effective_at="2026-11-07T14:00:00Z",
        account_ref="synthetic",
        top_k=2,
        entry_buffer=1,
        exit_buffer=1,
        name_cap="0.6",
        gross_cap="1",
        turnover_cap="0.2",
        drift_band="0.02",
        max_age_hours=24,
    )
    inputs = dict(
        declaration_sha256="b" * 64,
        account_ref="synthetic",
        current_weights={"A": "0.5"},
        target_weights={"A": "0.5"},
        universe=["A"],
        scheduled_review=False,
        sources={
            k: dict(
                available_at="2026-11-07T14:00:00Z",
                effective_at="2026-11-07T14:00:00Z",
                sha256="a" * 64,
            )
            for k in ["account", "pit", "universe", "model", "scores", "target"]
        },
    )
    inputs["sources"]["scores"]["parents"] = {
        k: "a" * 64 for k in ["pit", "universe", "model"]
    }
    inputs["sources"]["target"]["parents"] = {"scores": "a" * 64}
    assert review_decision(policy, inputs, NOW)["status"] == "maintain_candidate"
    inputs["sources"]["target"]["parents"] = {"scores": "c" * 64}
    assert review_decision(policy, inputs, NOW)["status"] == "blocked"
    inputs["sources"]["target"]["parents"] = {"scores": "a" * 64}
    inputs["sources"]["account"]["effective_at"] = "2020-01-01T00:00:00Z"
    assert review_decision(policy, inputs, NOW)["status"] == "blocked"
    inputs["sources"]["account"]["effective_at"] = "2026-11-07T14:00:00Z"
    inputs["target_weights"] = {"A": "0.55"}
    assert review_decision(policy, inputs, NOW)["status"] == "review_required"
    inputs["sources"]["pit"]["available_at"] = "2026-11-08T14:00:00Z"
    assert review_decision(policy, inputs, NOW)["status"] == "blocked"
    inputs["sources"]["pit"]["available_at"] = "2026-11-05T14:00:00Z"
    assert review_decision(policy, inputs, NOW)["status"] == "blocked"


def test_audit_rejects_tampered_declaration_before_output(tmp_path):
    from competition_tools.competition_review.cli import audit
    from competition_tools.crypto_evidence import digest

    declaration = tmp_path / "declaration"
    declaration.mkdir()
    records = []
    for name in ["declaration.json", "declaration.md", "declaration.zh-CN.md"]:
        p = declaration / name
        p.write_text("{}")
        records.append(dict(path=name, sha256=digest(p)))
    (declaration / "receipt.json").write_text(json.dumps(dict(files=records)))
    (declaration / "declaration.json").write_text("changed")
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    with pytest.raises(ValueError, match="RECEIPT_MISMATCH"):
        audit(declaration, snapshots, tmp_path / "output", NOW)
    assert not (tmp_path / "output").exists()


def test_invalid_policy_and_republished_old_evidence_cannot_maintain():
    from competition_tools.competition_review.decision import review_decision

    policy = dict(
        status="confirmed",
        account_ref="synthetic",
        top_k=True,
        entry_buffer="INVALID",
        exit_buffer=-5,
        name_cap="0.6",
        gross_cap="1",
        turnover_cap="0.2",
        drift_band="0.02",
        max_age_hours=24,
    )
    inputs = dict(
        declaration_sha256="b" * 64,
        account_ref="synthetic",
        current_weights={"A": "0.5"},
        target_weights={"A": "0.5"},
        universe=["A"],
        scheduled_review=False,
        sources={
            k: dict(
                available_at="2026-11-07T14:00:00Z",
                sha256="a" * 64,
                effective_at="2020-01-01T00:00:00Z",
            )
            for k in ["account", "pit", "universe", "model", "scores", "target"]
        },
    )
    result = review_decision(policy, inputs, NOW)
    assert result["status"] == "blocked"
    assert "POLICY_INVALID" in result["blockers"]
