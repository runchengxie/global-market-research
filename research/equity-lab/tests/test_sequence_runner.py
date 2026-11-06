import json
import pytest
from equity_lab.study.sequence.config import freeze_schedule
from equity_lab.study.sequence.artifacts import (
    create_bundle,
    seal_bundle,
    verify_bundle,
)


def test_fit_budget_counts_independent_members():
    schedule = freeze_schedule(folds=7)
    assert schedule["fits"] == 315
    with pytest.raises(ValueError, match="BUDGET"):
        freeze_schedule(folds=20)
    assert len(schedule["tasks"]) == 7 * 5 * 10


def test_bundle_is_exclusive_and_detects_corruption(tmp_path):
    path = tmp_path / "bundle"
    create_bundle(path, {"schema": "equity_lab.sequence_study.v1"})
    with pytest.raises(FileExistsError):
        create_bundle(path, {})
    (path / "result.json").write_text(json.dumps({"status": "partial"}))
    seal_bundle(path)
    assert verify_bundle(path)["files"] == 2
    (path / "result.json").write_text("{}")
    with pytest.raises(ValueError, match="INTEGRITY"):
        verify_bundle(path)


def test_installed_synthetic_run_roundtrip(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("exchange_calendars")
    from test_sequence_data import snapshot_fixture
    from equity_lab.study.sequence.samples import build_samples
    from equity_lab.study.sequence.protocol import make_folds
    from equity_lab.study.sequence.runner import run_study

    snap = snapshot_fixture(tmp_path)
    samples = build_samples(snap, 5)
    folds = make_folds(samples, fit=40, validation=20, test=20, minimum_test=10)[:1]
    schedule = freeze_schedule(
        1, seeds=[11], candidates=["cash", "holding", "sparse"], epochs=1, seconds=600
    )
    out = tmp_path / "run"
    summary = run_study(schedule, snap, samples, folds, out)
    assert summary["status"] == "completed"
    assert len(summary["completed"]) == 3
    assert summary["completed"][0]["zero_trade"] is True
    assert verify_bundle(out)["files"] > 10


def test_code_identity_is_bound_to_installed_module_not_cwd(tmp_path, monkeypatch):
    from equity_lab.study.sequence.artifacts import source_identity

    before = source_identity()
    monkeypatch.chdir(tmp_path)
    after = source_identity()
    assert before == after
    assert len(after["files"]) > 10


def test_source_identity_without_git(monkeypatch):
    import subprocess
    from equity_lab.study.sequence.artifacts import source_identity

    def absent(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "check_output", absent)
    identity = source_identity()
    assert identity["revision"] is None
    assert identity["files"]


def test_interrupted_run_seals_partial_summary(tmp_path, monkeypatch):
    pytest.importorskip("exchange_calendars")
    from test_sequence_data import snapshot_fixture
    from equity_lab.study.sequence.samples import build_samples
    from equity_lab.study.sequence.protocol import make_folds
    from equity_lab.study.sequence import runner

    snap = snapshot_fixture(tmp_path)
    samples = build_samples(snap, 5)
    folds = make_folds(samples, fit=40, validation=20, test=20, minimum_test=10)[:1]

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(runner, "fit_prediction", interrupt)
    summary = runner.run_study(
        freeze_schedule(1, seeds=[11], candidates=["cash"]),
        snap,
        samples,
        folds,
        tmp_path / "partial",
    )
    assert summary["status"] == "partial"
    assert len(summary["pending"]) == 1
    assert verify_bundle(tmp_path / "partial")["status"] == "verified"


def test_fixed_checkpoint_audit_is_separate_and_reproducible(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("exchange_calendars")
    from test_sequence_data import snapshot_fixture
    from equity_lab.study.sequence.samples import build_samples
    from equity_lab.study.sequence.protocol import make_folds
    from equity_lab.study.sequence.runner import run_study
    from equity_lab.study.sequence.interventions import audit_fitted_models

    snap = snapshot_fixture(tmp_path)
    samples = build_samples(snap, 5)
    folds = make_folds(samples, fit=40, validation=20, test=20, minimum_test=10)[:1]
    parent = tmp_path / "parent"
    run_study(
        freeze_schedule(1, seeds=[11], candidates=["dense", "sparse"], epochs=1),
        snap,
        samples,
        folds,
        parent,
    )
    records = audit_fitted_models(snap, parent, tmp_path / "audit")
    assert len(records) == 14
    assert {r["intervention"] for r in records} == {
        "equal",
        "drop-0",
        "drop-1",
        "drop-2",
        "only-0",
        "only-1",
        "only-2",
    }
    assert verify_bundle(parent)["status"] == "verified"
    assert verify_bundle(tmp_path / "audit")["status"] == "verified"
