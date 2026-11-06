import hashlib
import json
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("exchange_calendars")

from equity_lab.data import sequence_daily as daily  # noqa: E402
from equity_lab.study.sequence.samples import build_samples  # noqa: E402
from equity_lab.study.sequence.protocol import make_folds  # noqa: E402


def snapshot_fixture(tmp_path, count=120):
    schedule = daily.session_schedule("2023-01-03", "2026-10-20").iloc[:count]
    root = tmp_path / "input"
    (root / "normalized").mkdir(parents=True)
    files = []
    for symbol in ["AAPL", "MSFT", "SPY"]:
        price = 100 * np.exp(np.arange(count) * 0.001 + 0.02 * np.sin(np.arange(count)))
        frame = pd.DataFrame(
            dict(
                date=schedule.index,
                open=price,
                high=price * 1.02,
                low=price * 0.98,
                close=price * 1.001,
                volume=1000.0,
            )
        )
        path = root / "normalized" / f"{symbol}.csv"
        frame.to_csv(path, index=False)
        files.append(
            dict(
                path=f"normalized/{symbol}.csv",
                bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    spec = dict(
        source="ibkr_daily",
        market="US",
        calendar="XNYS",
        timezone="America/New_York",
        price_basis="split_adjusted",
        universe_status="fixed_current",
        quote_currency="USD",
        products=["AAPL", "MSFT"],
        benchmark="SPY",
        start=schedule.index[0],
        end=schedule.index[-1],
    )
    receipt = dict(status="acquired", spec_hash="fixture", coverage={}, gaps=[])
    manifest = dict(
        schema="competition.dataset_manifest.v2",
        spec=spec,
        receipt=receipt,
        status="acquired",
        accepted_research=False,
        spec_hash="fixture",
        files=files,
    )
    (root / "receipt.json").write_text(json.dumps(receipt))
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    return daily.load_daily_snapshot(path, daily.digest(path))


def test_next_open_sample_and_symbol_boundaries(tmp_path):
    snap = snapshot_fixture(tmp_path)
    sample = build_samples(snap, lookback=5)
    assert set(sample.audit.symbol) == {"AAPL", "MSFT"}
    assert sample.x.shape[1:] == (5, 10)
    row = sample.audit.iloc[0]
    bars = snap.frames[row.symbol]
    assert row.forward_return == pytest.approx(
        bars.loc[row.exit_session, "open"] / bars.loc[row.entry_session, "open"] - 1
    )
    assert row.feature_end < row.entry_session < row.exit_session
    assert row.available_ts < row.entry_ts
    assert (sample.audit.label_available_ts == sample.audit.exit_ts).all()


def test_snapshot_rejects_mutated_payload(tmp_path):
    snap = snapshot_fixture(tmp_path)
    (snap.root / "normalized/AAPL.csv").write_text("changed")
    with pytest.raises(ValueError, match="INTEGRITY"):
        snap.verify()


def test_duplicate_and_missing_session_rejected(tmp_path):
    snap = snapshot_fixture(tmp_path)
    frame = snap.frames["AAPL"].reset_index()
    with pytest.raises(ValueError, match="SESSION"):
        daily.validate_frame(pd.concat([frame, frame.iloc[:1]]), snap.schedule)
    with pytest.raises(ValueError, match="SESSION"):
        daily.validate_frame(frame.iloc[1:], snap.schedule)


def test_folds_purge_equal_cutoff_and_readiness(tmp_path):
    samples = build_samples(snapshot_fixture(tmp_path), 5)
    folds = make_folds(samples, fit=40, validation=20, test=20, minimum_test=10)
    assert folds
    for fold in folds:
        a = samples.audit
        assert (a.iloc[fold.fit].label_available_ts < fold.fit_cutoff).all()
        assert (
            a.iloc[fold.validation].label_available_ts < fold.selection_cutoff
        ).all()
        assert (a.iloc[fold.test].entry_ts > fold.ready_ts).all()
        assert set(fold.fit).isdisjoint(fold.test)
        assert len(set(a.iloc[fold.test].feature_end)) >= 10


def test_invalid_stock_features_cannot_shrink_pool(tmp_path):
    snap = snapshot_fixture(tmp_path)
    snap.frames["MSFT"]["volume"] = 0
    with pytest.raises(ValueError, match="FEATURE"):
        build_samples(snap, 5)
