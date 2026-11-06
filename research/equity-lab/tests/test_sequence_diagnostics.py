import pytest

pytest.importorskip("torch")
pytest.importorskip("exchange_calendars")
from equity_lab.study.sequence.diagnostics import diagnose_run  # noqa: E402
from equity_lab.study.sequence.artifacts import verify_bundle  # noqa: E402


def test_frozen_diagnostics_preserve_parent_and_select_on_validation(
    tmp_path, monkeypatch
):
    from test_sequence_data import snapshot_fixture
    from equity_lab.study.sequence.samples import build_samples
    from equity_lab.study.sequence.protocol import make_folds
    from equity_lab.study.sequence.runner import run_study
    from equity_lab.study.sequence.config import freeze_schedule

    snap = snapshot_fixture(tmp_path)
    samples = build_samples(snap, 5)
    folds = make_folds(samples, fit=40, validation=20, test=20, minimum_test=10)[:1]
    parent = tmp_path / "parent"
    run_study(
        freeze_schedule(
            1, seeds=[11], candidates=["matched", "equal", "dense", "sparse"], epochs=1
        ),
        snap,
        samples,
        folds,
        parent,
    )
    original = (parent / "checksums.json").read_bytes()
    summary = diagnose_run(snap, parent, tmp_path / "diagnostic")
    assert summary["status"] == "completed" and len(summary["records"]) == 4
    assert (parent / "checksums.json").read_bytes() == original
    for row in summary["records"]:
        assert row["selection_source"] == "validation_only"
        assert len(row["threshold_candidates"]) == 5
        assert set(row["accounts"]) == {
            "original",
            "constant_25",
            "constant_50",
            "validation_exposure",
            "validation_volatility",
            "causal_volatility_10",
            "validation_threshold",
        }
        assert row["test"]["count"] > 0
        assert row["validation"]["count"] > 0
    for row in summary["records"]:
        for fee, original in row["accounts"]["original"].items():
            assert original["realized_volatility_gap_to_model"] == 0
            assert original["realized_exposure_gap_to_model"] == 0
    assert verify_bundle(tmp_path / "diagnostic")["status"] == "verified"

    from equity_lab.study.sequence import diagnostics as module

    score = module._scores

    def mutate_parent(*args):
        result = score(*args)
        from equity_lab.study.sequence.artifacts import seal_bundle

        (parent / "changed.txt").write_text("changed during diagnosis")
        seal_bundle(parent)
        return result

    monkeypatch.setattr(module, "_scores", mutate_parent)
    changed = diagnose_run(snap, parent, tmp_path / "changed")
    assert changed["status"] == "invalid" and changed["reason"] == "INPUT_CHANGED"
    monkeypatch.setattr(module, "_scores", score)
    ticks = iter([0, *([2] * 100)])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(ticks))
    expired = diagnose_run(snap, parent, tmp_path / "expired", seconds=1)
    assert expired["status"] == "partial" and expired["reason"] == "WALL_CLOCK_BUDGET"
    assert verify_bundle(tmp_path / "expired")["status"] == "verified"
    monkeypatch.undo()

    def missing_input():
        raise FileNotFoundError("input disappeared")

    original_verify = snap.verify
    calls = 0

    def disappear_at_finalization():
        nonlocal calls
        calls += 1
        if calls > 1:
            missing_input()
        return original_verify()

    monkeypatch.setattr(snap, "verify", disappear_at_finalization)
    missing = diagnose_run(snap, parent, tmp_path / "missing-input")
    assert missing["status"] == "invalid" and missing["reason"] == "INPUT_CHANGED"
    assert verify_bundle(tmp_path / "missing-input")["status"] == "verified"


def test_diagnostic_budget_records_partial(tmp_path):
    with pytest.raises(ValueError, match="BUDGET"):
        diagnose_run(None, tmp_path / "missing", tmp_path / "out", seconds=0)
