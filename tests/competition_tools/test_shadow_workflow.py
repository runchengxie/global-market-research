"""Prospective records and explicitly attributed one-interval outcome arithmetic."""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from test_strategy_case import NOW, write

from competition_tools.crypto_evidence import digest, verify_seal

pytest_plugins = ["test_strategy_case"]

LATER = datetime(2026, 11, 11, tzinfo=timezone.utc)


def outcome(entry):
    return dict(
        schema="competition.shadow_outcome.v1",
        benchmark="SYNTHETIC",
        decision_sha256=digest(entry / "decision.json"),
        account_ref="paper",
        base_currency="USD",
        start="2026-11-09T00:00:00Z",
        end="2026-11-10T00:00:00Z",
        available_at="2026-11-10T01:00:00Z",
        returns={"1": "0.1"},
        non_stock_return="0.01",
        benchmark_return="0.02",
        one_way_cost_bps="10",
    )


def test_prepare_keeps_parameters_missing_and_separates_research(case, tmp_path):
    from competition_tools.competition_review.shadow import prepare

    path, _, _ = case
    out = tmp_path / "draft"
    r = prepare(path, out, now=NOW)
    assert r["status"] == "draft"
    assert r["benchmark"] is None and r["target_weights"] is None
    assert r["risk_limits"] is None
    assert set(r["research_lanes"]) == {"competition", "crypto", "moe"}
    assert r["execution_authorized"] is False
    verify_seal(out)
    assert (out / "report.zh-CN.md").exists()
    with pytest.raises(FileExistsError):
        prepare(path, out, now=NOW)


def test_record_uses_capture_time_and_preserves_blocked_not_maintain(case, tmp_path):
    from competition_tools.competition_review.shadow import record

    path, manifest, _ = case
    manifest["sources"] = {}
    write(path, manifest)
    out = tmp_path / "entry"
    r = record(path, out, now=NOW)
    assert r["recorded_at"] == NOW.isoformat()
    assert r["review"]["daily_review"]["status"] == "blocked"
    assert r["review"]["report_date"] == "2026-11-06"
    assert r["intent"] == "blocked_evidence_review"
    verify_seal(out)


def test_later_evaluation_is_exact_paired_arithmetic(case, tmp_path):
    from competition_tools.competition_review.shadow import record, evaluate

    entry = tmp_path / "entry"
    record(case[0], entry, now=NOW)
    source = tmp_path / "outcome.json"
    write(source, outcome(entry))
    r = evaluate(entry, source, tmp_path / "evaluation", now=LATER)
    assert Decimal(r["maintain_return"]) == Decimal(".055")
    assert Decimal(r["target_return_after_initial_cost"]) == Decimal(".0639")
    assert Decimal(r["paired_difference"]) == Decimal(".0089")
    assert Decimal(r["target_excess_over_benchmark"]) == Decimal(".0439")
    assert r["execution_authorized"] is False
    assert r["statistical_superiority_established"] is False


@pytest.mark.parametrize(
    "mode",
    [
        "blocked",
        "tampered_entry",
        "tampered_target",
        "early_start",
        "future_available",
        "wrong_hash",
        "wrong_currency",
        "wrong_account",
        "missing_return",
        "extra_return",
        "nonfinite",
        "below_minus_one",
        "cost_too_large",
    ],
)
def test_invalid_later_observations_never_produce_output(case, tmp_path, mode):
    from competition_tools.competition_review.shadow import record, evaluate

    path, manifest, paths = case
    if mode == "blocked":
        manifest["sources"] = {}
        write(path, manifest)
    entry = tmp_path / "entry"
    record(path, entry, now=NOW)
    o = outcome(entry)
    if mode == "tampered_entry":
        (entry / "decision.json").write_text("{}")
    elif mode == "tampered_target":
        paths["target"].write_text("{}")
    elif mode == "early_start":
        o["start"] = "2026-11-07T00:00:00Z"
    elif mode == "future_available":
        o["available_at"] = "2026-11-12T00:00:00Z"
    elif mode == "wrong_hash":
        o["decision_sha256"] = "a" * 64
    elif mode == "wrong_currency":
        o["base_currency"] = "SGD"
    elif mode == "wrong_account":
        o["account_ref"] = "other"
    elif mode == "missing_return":
        o["returns"] = {}
    elif mode == "extra_return":
        o["returns"]["2"] = ".1"
    elif mode == "nonfinite":
        o["returns"]["1"] = "NaN"
    elif mode == "below_minus_one":
        o["returns"]["1"] = "-1.01"
    elif mode == "cost_too_large":
        o["one_way_cost_bps"] = "10001"
    source = tmp_path / "outcome.json"
    write(source, o)
    out = tmp_path / "evaluation"
    with pytest.raises(ValueError):
        evaluate(entry, source, out, now=LATER)
    assert not out.exists()


@pytest.fixture(autouse=True)
def registered_window(case):
    path, manifest, _ = case
    manifest["shadow_window"] = {
        "start": "2026-11-09T00:00:00Z",
        "end": "2026-11-10T00:00:00Z",
    }
    write(path, manifest)


@pytest.mark.parametrize(
    "mode",
    ["changed_benchmark", "changed_cost", "changed_window", "unregistered_window"],
)
def test_later_evaluation_cannot_select_protocol_after_results(case, tmp_path, mode):
    from competition_tools.competition_review.shadow import record, evaluate

    path, manifest, _ = case
    if mode == "unregistered_window":
        manifest.pop("shadow_window")
        write(path, manifest)
    entry = tmp_path / "entry"
    record(path, entry, now=NOW)
    o = outcome(entry)
    if mode == "changed_benchmark":
        o["benchmark"] = "OTHER"
    elif mode == "changed_cost":
        o["one_way_cost_bps"] = "0"
    elif mode == "changed_window":
        o["end"] = "2026-11-10T00:30:00Z"
    source = tmp_path / "outcome.json"
    write(source, o)
    with pytest.raises(ValueError):
        evaluate(entry, source, tmp_path / "bad", now=LATER)
    assert not (tmp_path / "bad").exists()
