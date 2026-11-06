import pytest

pytest.importorskip("torch")
pytest.importorskip("exchange_calendars")
from equity_lab.study.sequence.diagnostics import diagnose_run  # noqa: E402
from equity_lab.study.sequence.artifacts import verify_bundle  # noqa: E402


def test_frozen_diagnostics_preserve_parent_and_select_on_validation(tmp_path):
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
    assert verify_bundle(tmp_path / "diagnostic")["status"] == "verified"


def test_diagnostic_budget_records_partial(tmp_path):
    with pytest.raises(ValueError, match="BUDGET"):
        diagnose_run(None, tmp_path / "missing", tmp_path / "out", seconds=0)
