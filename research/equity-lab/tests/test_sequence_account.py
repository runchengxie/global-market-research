import numpy as np
import pandas as pd
import pytest
from equity_lab.study.sequence.account import replay_sequence
from equity_lab.study.sequence.metrics import paired_report


def test_cash_and_initial_drawdown():
    rows = pd.DataFrame(
        dict(
            symbol=["A"] * 2,
            entry_session=["a", "b"],
            exit_session=["b", "c"],
            entry_price=[100.0, 90.0],
            exit_price=[90.0, 81.0],
            prediction=[1, 1],
        )
    )
    result = replay_sequence(rows, fee_bps=0)
    assert result["return"] == pytest.approx(-0.19)
    assert result["drawdown"] == pytest.approx(-0.19)
    rows["prediction"] = 0
    quiet = replay_sequence(rows, fee_bps=5)
    assert quiet["return"] == 0
    assert quiet["trades"] == 0
    assert quiet["sharpe"] is None


def test_entry_and_terminal_fees_and_missing_mark():
    rows = pd.DataFrame(
        dict(
            symbol=["A"],
            entry_session=["a"],
            exit_session=["b"],
            entry_price=[100.0],
            exit_price=[100.0],
            prediction=[1],
        )
    )
    result = replay_sequence(rows, fee_bps=5)
    assert result["return"] == pytest.approx((1 - 0.0005) / (1 + 0.0005) - 1)
    assert result["trades"] == 2
    rows.loc[0, "exit_price"] = np.nan
    with pytest.raises(ValueError, match="PRICE"):
        replay_sequence(rows, fee_bps=5)


def test_paired_resampling_preserves_fold_boundaries():
    records = [
        dict(fold=f, date=d, model=m, value=float(d) + (m == "b"))
        for f in [0, 1]
        for d in range(30)
        for m in ["a", "b"]
    ]
    report = paired_report(records, reference="a", draws=40)
    assert report["b"]["difference"] == 1
    assert report["b"]["interval"] == [1.0, 1.0]
