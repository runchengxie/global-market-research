import pytest

pytest.importorskip("torch")
pytest.importorskip("exchange_calendars")
from equity_lab.study.sequence.target_study import (
    freeze_target_schedule,
    run_target_study,
)  # noqa:E402
from equity_lab.study.sequence.target_analysis import continuation_rule  # noqa:E402


def test_target_schedule_counts_unique_linear_fits_and_rejects_overbudget():
    plan = freeze_target_schedule(7)
    assert plan["fits"] == 140 and len(plan["tasks"]) == 175
    linear = [t for t in plan["tasks"] if t["model"] == "linear"]
    assert len(linear) == 14 and {t["seed"] for t in linear} == {11}
    with pytest.raises(ValueError, match="BUDGET"):
        freeze_target_schedule(7, max_fits=139)


def test_missing_gate_evidence_never_passes():
    result = continuation_rule({}, [], 7)
    assert result["status"] == "insufficient_evidence"
    assert result["expand_moe"] is False


def test_complete_small_target_bundle_and_interrupt(tmp_path, monkeypatch):
    from test_sequence_data import snapshot_fixture
    from equity_lab.study.sequence.samples import build_samples
    from equity_lab.study.sequence.protocol import make_folds
    from equity_lab.study.sequence.artifacts import verify_bundle

    snap = snapshot_fixture(tmp_path)
    samples = build_samples(snap, 5)
    folds = make_folds(samples, fit=40, validation=20, test=20, minimum_test=10)[:1]
    plan = freeze_target_schedule(1, seeds=[11], epochs=1)
    out = tmp_path / "out"
    report = run_target_study(plan, snap, samples, folds, out)
    assert report["status"] == "completed" and len(report["completed"]) == 13
    assert report["fits_completed"] == 8
    assert verify_bundle(out)["status"] == "verified"
    from equity_lab.study.sequence.target_analysis import analyze_targets

    analysis = analyze_targets(report, draws=20)
    assert (
        analysis["objectives"]["regression"]["continuation"]["status"]
        == "insufficient_evidence"
    )
    assert analysis["objectives"]["classification"]["complete"] is True
    # A seven-fold smoke/custom plan is not the frozen three-seed,30-epoch screen.
    custom = dict(
        report,
        schedule=freeze_target_schedule(7, seeds=[11], epochs=1),
        completed=[
            dict(row, fold=fold) for fold in range(7) for row in report["completed"]
        ],
    )
    custom_analysis = analyze_targets(custom, draws=5)
    assert (
        custom_analysis["objectives"]["classification"]["continuation"]["status"]
        == "insufficient_evidence"
    )

    for record in report["completed"]:
        if record["objective"] == "regression":
            assert record["metrics"]["brier"] is None
    import equity_lab.study.sequence.target_study as module

    monkeypatch.setattr(
        module, "fit_target", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    partial = run_target_study(plan, snap, samples, folds, tmp_path / "partial")
    assert partial["status"] == "partial" and partial["reason"] == "INTERRUPTED"
    assert verify_bundle(tmp_path / "partial")["status"] == "verified"


def test_rule_fails_each_contrast_and_never_authorizes_expansion():
    from copy import deepcopy

    contrasts = {
        name: dict(
            difference=0.001,
            interval=[0.0001, 0.002],
            fee20_difference=0.0001,
            positive_folds=5,
        )
        for name in ["linear", "matched", "equal", "exposure", "prior"]
    }
    good = continuation_rule(contrasts, list(range(7)))
    assert good["status"] == "promising_retrospective" and good["expand_moe"] is False
    for name in ["linear", "matched", "equal"]:
        changed = deepcopy(contrasts)
        changed[name]["positive_folds"] = 4
        assert (
            continuation_rule(changed, list(range(7)))["status"] == "continue_deferred"
        )
    contrasts["prior"]["interval"] = [-0.001, 0.001]
    assert continuation_rule(contrasts, list(range(7)))["status"] == "continue_deferred"


def test_calendar_is_a_model_not_observed_availability():
    from equity_lab.study.sequence.target_cli import future_calendar

    value = future_calendar("2026-11-09", "2027-02-05")
    assert (
        value["observed_availability"] is False and value["registered_holdout"] is False
    )
    assert value["sessions"][0]["date"] == "2026-11-09"
    assert value["final_entry"]["date"] > value["sessions"][-1]["date"]
    assert value["final_exit"]["date"] > value["final_entry"]["date"]


def test_analysis_interruption_after_compute_cannot_seal_completed(
    tmp_path, monkeypatch
):
    import json
    from equity_lab.study.sequence import target_cli
    from equity_lab.study.sequence.artifacts import (
        create_bundle,
        seal_bundle,
        verify_bundle,
    )

    parent = tmp_path / "parent"
    create_bundle(parent, {"schema": "test"})
    (parent / "summary.json").write_text(
        json.dumps({"schema": "equity_lab.sequence_target_study.v1"})
    )
    seal_bundle(parent)
    checks = 0
    real_verify = target_cli.verify_bundle

    def interrupt_after_compute(path):
        nonlocal checks
        checks += 1
        if checks == 2:
            raise KeyboardInterrupt
        return real_verify(path)

    monkeypatch.setattr(target_cli, "verify_bundle", interrupt_after_compute)
    monkeypatch.setattr(
        target_cli,
        "analyze_targets",
        lambda summary: {
            "status": "completed",
            "objectives": {
                "classification": {
                    "continuation": {"status": "promising_retrospective"}
                }
            },
        },
    )
    out = tmp_path / "analysis"
    result = target_cli.analyze_run(parent, out)
    assert result["status"] == "partial" and result["reason"] == "INTERRUPTED"
    assert "promising_retrospective" not in (out / "analysis.json").read_text()
    assert verify_bundle(out)["status"] == "verified"


def test_analysis_output_inside_parent_is_rejected_without_mutating_it(
    tmp_path, monkeypatch
):
    import json
    from equity_lab.study.sequence import target_cli
    from equity_lab.study.sequence.artifacts import (
        create_bundle,
        seal_bundle,
        verify_bundle,
    )

    parent = tmp_path / "parent"
    create_bundle(parent, {"schema": "test"})
    (parent / "summary.json").write_text(
        json.dumps({"schema": "equity_lab.sequence_target_study.v1"})
    )
    seal_bundle(parent)
    before = (parent / "checksums.json").read_bytes()
    monkeypatch.setattr(
        target_cli,
        "analyze_targets",
        lambda summary: {"status": "completed", "objectives": {}},
    )
    with pytest.raises(ValueError, match="SEPARATE"):
        target_cli.analyze_run(parent, parent / "analysis")
    assert (parent / "checksums.json").read_bytes() == before
    assert not (parent / "analysis").exists()
    assert verify_bundle(parent)["status"] == "verified"
