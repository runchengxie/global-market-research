"""Synthetic sealed report aggregation, not independent price/replay evidence."""

from datetime import datetime, timezone
from pathlib import Path
import json
import pytest
from competition_tools.crypto_evidence import digest, seal, verify_seal

NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)
ARMS = [
    "fixed_reference",
    "calibration_fixed",
    "volatility_control",
    "buffer_sensitivity",
    "hindsight_exposure_matched",
]


def save(root, name, value):
    root.mkdir(parents=True)
    (root / name).write_text(json.dumps(value))
    seal(root)


def replace(root, name, value):
    (root / name).write_text(json.dumps(value))
    (root / "seal.json").unlink()
    seal(root)


@pytest.fixture
def bundle(tmp_path):
    import exchange_calendars as xc

    core = dict(
        lookback_returns=20,
        annualization=252,
        target_volatility=0.1,
        cap=1.0,
        fixed_reference_weight=0.4,
        one_way_cost_bps=[0, 10, 25],
        buffer_sensitivity=0.05,
        cash_return=0,
        leverage_allowed=False,
        parameter_optimization=False,
        execution_authorized=False,
        match_tolerance=1e-7,
    )
    old = dict(
        core,
        schema="competition.volatility_study_protocol.v1",
        calibration_start="2024-01-02",
        calibration_end="2024-12-31",
        evaluation_start="2025-01-02",
        evaluation_end="2026-11-06",
        frozen_at="2026-11-07T00:00:00Z",
    )
    original = tmp_path / "original"
    save(original, "protocol.json", old)
    cal = xc.get_calendar("XNYS", start="2014-01-01", end="2026-12-31").schedule
    episodes = []
    for year in [2014, 2015, 2016, 2026]:
        dates = [
            d.date().isoformat()
            for d in cal.index
            if d.year == year and (year != 2026 or d.date().isoformat() <= "2026-11-06")
        ]
        episodes.append(
            dict(
                id=str(year),
                evaluation_start=dates[0],
                evaluation_end=dates[-1],
                full_calendar_year=year != 2026,
                previously_examined=year == 2026,
                include_in_decision=year != 2026,
            )
        )
    intent = dict(
        schema="competition.volatility_robustness_intent.v1",
        frozen_at="2026-11-08T00:00:00Z",
        original_protocol_sha256=digest(original / "protocol.json"),
        core_parameters=core,
        calibration_start="2013-01-02",
        calibration_end="2013-12-31",
        episodes=episodes,
        decision_fees=[10, 25],
        required_share_numerator=2,
        required_share_denominator=3,
        numerical_tolerance=1e-8,
        material_improvement=1e-4,
        execution_authorized=False,
    )
    plan = tmp_path / "intent"
    save(plan, "intent.json", intent)
    src = tmp_path / "source"
    src.mkdir()
    (src / "data.json").write_text(json.dumps(dict(synthetic=True)))
    (src / "receipt.json").write_text(
        json.dumps(
            dict(
                records=[
                    dict(
                        symbol="USMV",
                        status="received",
                        sha256=digest(src / "data.json"),
                        requested_at="2026-11-08T00:10:00Z",
                        finished_at="2026-11-08T00:20:00Z",
                    )
                ]
            )
        )
    )
    seal(src)
    manifest = tmp_path / "inputs"
    save(
        manifest,
        "manifest.json",
        dict(
            schema="competition.etf_rehearsal_inputs.v1",
            sources={
                k: dict(path=str(src / "data.json"), sha256=digest(src / "data.json"))
                for k in ["usmv", "japan", "usdsgd", "usdjpy"]
            },
        ),
    )
    entries = []
    studies = []
    for e in episodes:
        p = dict(
            core,
            schema="competition.volatility_study_protocol.v1",
            calibration_start=intent["calibration_start"],
            calibration_end=intent["calibration_end"],
            evaluation_start=e["evaluation_start"],
            evaluation_end=e["evaluation_end"],
            manifest_sha256=digest(manifest / "manifest.json"),
            intent_sha256=digest(plan / "intent.json"),
            frozen_at="2026-11-08T01:00:00Z",
            symbol="USMV",
            currency="USD",
        )
        cases = []
        for fee in [0, 10, 25]:
            for arm in ARMS:
                metrics = dict(
                    total_return=0.10 if arm == "volatility_control" else 0.09,
                    maximum_drawdown=-0.10 if arm == "volatility_control" else -0.11,
                    mean_exposure=0.5,
                    sum_trade_turnover=1.0,
                )
                cases.append(
                    dict(
                        arm=arm,
                        one_way_cost_bps=fee,
                        hindsight_nontradable=arm == "hindsight_exposure_matched",
                        match_residual=0
                        if arm == "hindsight_exposure_matched"
                        else None,
                        result=dict(metrics=metrics),
                    )
                )
        v = dict(
            schema="competition.volatility_study.v1",
            recorded_at="2026-11-08T02:00:00Z",
            protocol=p,
            source_manifest_sha256=digest(manifest / "manifest.json"),
            used_source_sha256=digest(src / "data.json"),
            currency="USD",
            cases=cases,
            accepted_research=False,
            actual_account_performance=False,
            execution_authorized=False,
        )
        root = tmp_path / ("study-" + e["id"])
        save(root, "study.json", v)
        studies.append((root, v))
        entries.append(
            dict(id=e["id"], root=str(root), study_sha256=digest(root / "study.json"))
        )
    runs = dict(
        schema="competition.volatility_robustness_runs.v1",
        recorded_at="2026-11-08T03:00:00Z",
        intent_sha256=digest(plan / "intent.json"),
        source_manifest_sha256=digest(manifest / "manifest.json"),
        source_manifest_file=str(manifest / "manifest.json"),
        entries=entries,
    )
    runroot = tmp_path / "runs"
    save(runroot, "runs.json", runs)
    return plan, original, runroot, intent, runs, studies


def capture(bundle, out):
    from competition_tools.competition_review.volatility_robustness import run

    return run(bundle[0], bundle[1], bundle[2], out, now=NOW)


def refresh(bundle):
    for i, (root, v) in enumerate(bundle[5]):
        replace(root, "study.json", v)
        bundle[4]["entries"][i]["study_sha256"] = digest(root / "study.json")
    replace(bundle[2], "runs.json", bundle[4])


def test_all_planned_rows_majority_and_partial_exclusion(bundle, tmp_path):
    r = capture(bundle, tmp_path / "result")
    assert r["new_full_episodes"] == 3 and r["required_passes"] == 2
    assert r["research_decision"] == "continue_candidate_under_frozen_rule"
    assert r["independent_source_status"] == "not_supplied"
    assert r["adoption_ready"] is False and r["execution_authorized"] is False
    assert len(r["comparisons"]) == 12
    assert all(
        not x["include_in_decision"]
        for x in r["comparisons"]
        if x["episode_id"] == "2026"
    )
    verify_seal(tmp_path / "result")
    with pytest.raises(FileExistsError):
        capture(bundle, tmp_path / "result")


def test_lower_return_cannot_be_hidden_by_less_negative_drawdown(bundle, tmp_path):
    # Two of three new episodes fail return dominance despite improved drawdown.
    for _, v in bundle[5][:2]:
        for c in v["cases"]:
            if c["arm"] == "volatility_control":
                c["result"]["metrics"]["total_return"] = 0.08
    refresh(bundle)
    r = capture(bundle, tmp_path / "result")
    assert r["research_decision"] == "retire_primary_candidate_under_frozen_rule"
    assert all(x["passing_episodes"] == 1 for x in r["fee_summaries"])


def test_missing_episode_or_fee_remains_unknown(bundle, tmp_path):
    bundle[4]["entries"].pop()
    replace(bundle[2], "runs.json", bundle[4])
    r = capture(bundle, tmp_path / "missing-year")
    assert r["research_decision"] == "unknown_incomplete_plan"
    assert r["missing_episode_ids"] == ["2026"]


@pytest.mark.parametrize(
    "mode",
    ["duplicate", "core", "source", "match", "future", "partial_flag", "identity"],
)
def test_inconsistent_bound_inputs_rejected_before_output(bundle, tmp_path, mode):
    if mode == "duplicate":
        bundle[4]["entries"].append(bundle[4]["entries"][0])
        replace(bundle[2], "runs.json", bundle[4])
    elif mode == "partial_flag":
        bundle[3]["episodes"][0]["full_calendar_year"] = False
        replace(bundle[0], "intent.json", bundle[3])
        bundle[4]["intent_sha256"] = digest(bundle[0] / "intent.json")
        for _, v in bundle[5]:
            v["protocol"]["intent_sha256"] = bundle[4]["intent_sha256"]
        refresh(bundle)
    else:
        v = bundle[5][0][1]
        if mode == "identity":
            v["protocol"]["symbol"] = "OTHER"
        elif mode == "core":
            v["protocol"]["target_volatility"] = 0.2
        elif mode == "source":
            v["source_manifest_sha256"] = "a" * 64
        elif mode == "match":
            next(c for c in v["cases"] if c["arm"] == "hindsight_exposure_matched")[
                "match_residual"
            ] = 0.01
        elif mode == "future":
            v["recorded_at"] = "2027-01-01T00:00:00Z"
        refresh(bundle)
    with pytest.raises(ValueError):
        capture(bundle, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_integer_ceiling_is_not_rounded_down():
    from competition_tools.competition_review.volatility_robustness import (
        required_passes,
    )

    assert required_passes(4, 2, 3) == 3
    assert required_passes(10, 2, 3) == 7


def test_missing_sensitivity_fee_also_blocks_complete_plan(bundle, tmp_path):
    bundle[5][0][1]["cases"] = [
        c for c in bundle[5][0][1]["cases"] if c["one_way_cost_bps"] != 0
    ]
    refresh(bundle)
    r = capture(bundle, tmp_path / "result")
    assert r["research_decision"] == "unknown_incomplete_plan"
    assert r["all_planned_episodes_complete"] is False


def test_partial_independent_evidence_never_becomes_adoption(bundle, tmp_path):
    from competition_tools.competition_review.volatility_robustness import run

    root = tmp_path / "corroboration"
    save(
        root,
        "corroboration.json",
        dict(
            schema="competition.volatility_source_corroboration.v1",
            manifest_sha256=bundle[4]["source_manifest_sha256"],
            comparison_scope="issuer_nav_and_distributions_not_market_ohlc",
            independent_upstream_verified=False,
            compatible_adjusted_ohlc=False,
        ),
    )
    r = run(
        bundle[0],
        bundle[1],
        bundle[2],
        tmp_path / "result",
        corroboration_root=root,
        now=NOW,
    )
    assert r["independent_source_status"] == "partial_attributed_corroboration"
    assert r["adoption_ready"] is False


def test_better_return_with_worse_drawdown_is_not_dominance(bundle, tmp_path):
    for _, v in bundle[5][:2]:
        for c in v["cases"]:
            if c["arm"] == "volatility_control":
                c["result"]["metrics"]["maximum_drawdown"] = -0.12
    refresh(bundle)
    r = capture(bundle, tmp_path / "result")
    assert r["research_decision"] == "retire_primary_candidate_under_frozen_rule"


def test_rewriting_frozen_core_cannot_replace_original_parameters(bundle, tmp_path):
    bundle[3]["core_parameters"]["target_volatility"] = 0.2
    replace(bundle[0], "intent.json", bundle[3])
    bundle[4]["intent_sha256"] = digest(bundle[0] / "intent.json")
    for _, v in bundle[5]:
        v["protocol"]["intent_sha256"] = bundle[4]["intent_sha256"]
        v["protocol"]["target_volatility"] = 0.2
    refresh(bundle)
    with pytest.raises(ValueError, match="ORIGINAL_CORE_MISMATCH"):
        capture(bundle, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_changed_source_bytes_rejected(bundle, tmp_path):
    manifest = json.loads(Path(bundle[4]["source_manifest_file"]).read_text())
    Path(manifest["sources"]["usmv"]["path"]).write_text("{}")
    with pytest.raises(ValueError):
        capture(bundle, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
