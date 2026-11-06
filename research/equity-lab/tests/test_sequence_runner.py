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
    pytest.importorskip('torch')
    from test_sequence_data import snapshot_fixture
    from equity_lab.study.sequence.samples import build_samples
    from equity_lab.study.sequence.protocol import make_folds
    from equity_lab.study.sequence.runner import run_study
    snap = snapshot_fixture(tmp_path)
    samples = build_samples(snap, 5)
    folds = make_folds(samples, fit=40, validation=20, test=20, minimum_test=10)[:1]
    schedule = freeze_schedule(1, seeds=[11], candidates=['cash','holding','sparse'], epochs=1, seconds=600)
    out = tmp_path/'run'
    summary = run_study(schedule, snap, samples, folds, out)
    assert summary['status'] == 'completed'
    assert len(summary['completed']) == 3
    assert summary['completed'][0]['zero_trade'] is True
    assert verify_bundle(out)['files'] > 10
