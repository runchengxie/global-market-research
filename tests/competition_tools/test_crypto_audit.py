from datetime import datetime, timezone
import pytest
from competition_tools.evaluation.crypto_audit import audit_receipts


def test_reconstruct_score_and_reject_duplicate_or_future():
    def t(h):
        return f"2026-11-07T{h:02}:00:00+00:00"

    forecast = dict(
        id="f",
        candidate="price_only-1h",
        asset="BTCUSDT",
        generated_at=t(1),
        feature_cutoff=t(1),
        entry_at=t(2),
        exit_at=t(3),
        prediction=0.02,
        prior_prediction=0.0,
    )
    market = {
        "prices": {
            "BTCUSDT": [dict(time_open=t(2), open=100), dict(time_open=t(3), open=101)]
        }
    }
    score = dict(
        forecast_id="f",
        scored_at=t(4),
        target=0.01,
        squared_error=0.0001,
        prior_squared_error=0.0001,
    )
    rows = [
        (
            dict(
                captured_at=t(1),
                status="completed",
                committed_forecasts=[forecast],
                scored_forecasts=[],
                observed_bars=[],
                revisions=[],
            ),
            market,
        ),
        (
            dict(
                captured_at=t(4),
                status="completed",
                committed_forecasts=[],
                scored_forecasts=[score],
                observed_bars=[],
                revisions=[],
            ),
            market,
        ),
    ]
    result = audit_receipts(rows, datetime(2026, 11, 7, 5, tzinfo=timezone.utc))
    assert (
        result["scored"] == 1
        and result["committed"] == 1
        and result["mse"] == pytest.approx(0.0001)
    )
    with pytest.raises(ValueError, match="DUPLICATE"):
        audit_receipts(
            [rows[0], rows[0], rows[1]], datetime(2026, 11, 7, 5, tzinfo=timezone.utc)
        )
    score["squared_error"] = 0
    with pytest.raises(ValueError, match="SCORE"):
        audit_receipts(rows, datetime(2026, 11, 7, 5, tzinfo=timezone.utc))
    score["squared_error"] = 0.0001
    forecast["generated_at"] = t(3)
    with pytest.raises(ValueError, match="DEADLINE"):
        audit_receipts(rows, datetime(2026, 11, 7, 5, tzinfo=timezone.utc))


def test_missing_score_prices_cannot_be_accepted():
    # An arbitrary scored identifier must bind to an earlier committed forecast.
    row = dict(
        captured_at="2026-11-07T04:00:00Z",
        status="completed",
        committed_forecasts=[],
        scored_forecasts=[{"forecast_id": "unknown"}],
        observed_bars=[],
        revisions=[],
    )
    with pytest.raises(ValueError, match="UNKNOWN"):
        audit_receipts(
            [(row, {"prices": {}})], datetime(2026, 11, 7, 5, tzinfo=timezone.utc)
        )
