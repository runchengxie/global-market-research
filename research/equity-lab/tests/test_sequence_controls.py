import numpy as np
import pandas as pd
import pytest
from equity_lab.study.sequence.account import replay_sequence, replay_allocations
from equity_lab.study.sequence.controls import (
    score_diagnostics,
    choose_threshold,
    validation_controls,
)


def bars():
    return pd.DataFrame(
        dict(
            symbol=["A", "A"],
            entry_session=["a", "b"],
            exit_session=["b", "c"],
            entry_price=[100.0, 110.0],
            exit_price=[110.0, 99.0],
            prediction=[1, 1],
        )
    )


def test_fractional_cash_fees_and_binary_parity():
    rows = bars()
    rows["allocation"] = rows.prediction.astype(float)
    old = replay_sequence(rows, 5)
    new = replay_allocations(rows, 5)
    assert old == new
    rows["allocation"] = 0.5
    half = replay_allocations(rows, 0)
    assert half["return"] == pytest.approx(1.05 * 0.95 - 1)
    assert half["exposure"] == 0.5
    assert half["marks"][0]["cash"] > 0
    for account in [old, new, half]:
        final = account["marks"][-1]
        assert final["cash"] == final["equity"]
        assert final["marked_exposure"] == 0
        assert final["open_exposure"] > 0
    for weight in [-0.01, 1.01, np.nan]:
        rows["allocation"] = weight
        with pytest.raises(ValueError, match="ALLOCATION"):
            replay_allocations(rows, 5)


def test_score_counts_and_one_class_are_explicit():
    pytest.importorskip("sklearn")
    d = score_diagnostics([0, 0], [0.4, 0.45])
    assert d["above_cutoff"] == 0 and d["score_max"] == 0.45
    assert d["auc"] is None
    assert d["base_rate"] == 0


def test_threshold_and_controls_depend_on_validation_only():
    val = bars()
    val["probability"] = [0.4, 0.6]
    threshold, grid = choose_threshold(val)
    assert threshold in [0.35, 0.425, 0.5, 0.575, 0.65] and len(grid) == 5
    controls = validation_controls(val)
    assert 0 <= controls["exposure"] <= 1
    assert 0 <= controls["volatility"] <= 1
    # Caller supplies no test outcomes to either selector.
    val["probability"] = 0.1
    zero = validation_controls(val)
    assert zero["exposure"] == 0 and zero["volatility"] == 0


def test_causal_volatility_ignores_future_close(tmp_path):
    pytest.importorskip("exchange_calendars")
    from test_sequence_data import snapshot_fixture
    from equity_lab.study.sequence.samples import build_samples
    from equity_lab.study.sequence.controls import causal_volatility_weights

    snap = snapshot_fixture(tmp_path)
    audit = build_samples(snap, 5).audit.iloc[:10].copy()
    expected = causal_volatility_weights(snap, audit)
    cutoff = audit.feature_end.max()
    for frame in snap.frames.values():
        frame.loc[frame.index > cutoff, "close"] *= 20
    assert np.array_equal(expected, causal_volatility_weights(snap, audit))
