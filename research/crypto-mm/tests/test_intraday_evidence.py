from datetime import datetime, timezone, timedelta
import numpy as np
import pytest

pytest.importorskip("sklearn")
from crypto_mm.intraday.features import price_features, factor_at, split_indices
from crypto_mm.intraday.study import cash_account, fit_model, predict_model


def bars(count=200, step=1):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [
        dict(
            asset="BTCUSDT",
            time_open=(start + timedelta(hours=i * step)).isoformat(),
            interval_end=(start + timedelta(hours=(i + 1) * step)).isoformat(),
            open=100 + i,
            high=102 + i,
            low=99 + i,
            close=101 + i,
            volume=2 + i * 0.01,
        )
        for i in range(count)
    ]


def test_features_use_one_bar_and_hour_scaled_windows():
    x = price_features(bars(80, 4), 4)
    assert x[41] is None and len(x[42]) == 7
    assert x[42][0] == pytest.approx(143 / 142 - 1)
    assert x[42][2] == pytest.approx(143 / 101 - 1)


def test_unverified_factor_proxy_never_backfills_period():
    rows = [{"period_end": datetime(2025, 1, 2, tzinfo=timezone.utc), "value": 3.0}]
    assert factor_at(rows, datetime(2025, 1, 2, 23, tzinfo=timezone.utc), 24) is None
    assert factor_at(rows, datetime(2025, 1, 3, tzinfo=timezone.utc), 24) == 3
    assert factor_at(rows, datetime(2025, 1, 4, tzinfo=timezone.utc), 24) is None


def test_purge_labels_reaching_first_test_decision():
    times = [
        datetime(2026, 4, 1, tzinfo=timezone.utc) + timedelta(hours=i)
        for i in range(-4, 3)
    ]
    fit, test = split_indices(
        times,
        1,
        datetime(2026, 4, 1, tzinfo=timezone.utc),
        datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    assert list(fit) == [0, 1] and list(test) == [4, 5, 6]


def test_cash_ledger_initial_peak_first_and_terminal_fees():
    result = cash_account([100, 90], [90, 81], [1, 1], 0)
    assert result["equity"][-1] == pytest.approx(0.81)
    assert result["max_drawdown"] == pytest.approx(-0.19)
    fee = cash_account([100], [100], [1], 10)
    assert fee["equity"][-1] == pytest.approx(0.999 / 1.001)
    assert fee["turnover"] > 1.99
    assert cash_account([100], [110], [0], 25)["equity"] == [1.0]


def test_model_reconstruction_and_fit_only_scaling():
    x = np.array([[1.0, 2.0], [2.0, 4.0], [3.0, 5.0]])
    y = np.array([0.01, 0.02, 0.04])
    m = fit_model(x, y, ["a", "b"])
    assert m["x_mean"] == pytest.approx(x.mean(axis=0))
    prediction = predict_model(m, np.array([[10000.0, -10000.0]]))
    assert np.isfinite(prediction).all() and m["x_mean"] == pytest.approx(
        x.mean(axis=0)
    )
    import json

    assert predict_model(json.loads(json.dumps(m)), x) == pytest.approx(
        predict_model(m, x), abs=1e-12
    )


def test_full_bar_entry_delay_and_common_factor_dates():
    from crypto_mm.intraday.features import samples
    from crypto_mm.intraday.inputs import INDICATORS

    source = bars(400)
    series = [
        dict(
            period_end=datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=i),
            value=float(i),
        )
        for i in range(30)
    ]
    factors = {("BTCUSDT", i): series for i in INDICATORS}
    result = samples(source, 1, factors, INDICATORS)
    first = result[0]
    assert first["entry_time"] - first["time"] == timedelta(hours=1)
    index = next(
        i
        for i, r in enumerate(source)
        if datetime.fromisoformat(r["interval_end"]) == first["time"]
    )
    assert first["entry"] == source[index + 2]["open"]
    assert first["exit"] == source[index + 3]["open"]
    assert (
        first["features"]["factor_proxy_24h"][-1]
        > first["features"]["factor_shift_7d"][-1]
    )


def test_failed_plan_cannot_reset_fit_budget_in_another_directory(
    tmp_path, monkeypatch
):
    import crypto_mm.intraday.study as study
    from crypto_mm.intraday.inputs import seal, sha, read

    dataset = tmp_path / "data"
    dataset.mkdir()
    (dataset / "manifest.json").write_text("{}")
    seal(dataset)
    sentiment = tmp_path / "factor.json"
    sentiment.write_text("[]")
    study.freeze_screen(dataset, sentiment, sha(sentiment), tmp_path / "plan", "a" * 40)

    def fail(path):
        raise ValueError("bad source")

    monkeypatch.setattr(study, "load_prices", fail)
    result = study.run_screen(tmp_path / "plan/plan.json", tmp_path / "run")
    assert (
        result["status"] == "partial"
        and result["fit_count"] == 0
        and result["summary"] == []
    )
    assert read(tmp_path / "run/ledger.json")["status"] == "partial"
    with pytest.raises(FileExistsError):
        study.run_screen(tmp_path / "plan/plan.json", tmp_path / "another")
    assert not (tmp_path / "another").exists()


def test_frozen_forecast_is_committed_before_future_entry(tmp_path):
    from crypto_mm.intraday.forecast import forecast_capture
    from crypto_mm.intraday.inputs import write, sha

    source = bars(400)
    x = np.tile(np.arange(7, dtype=float), (30, 1))
    y = np.linspace(0.001, 0.01, 30)
    from crypto_mm.intraday.features import NAMES

    model = fit_model(x, y, NAMES)
    model.update(step_hours=1, arm="price_only", fit_last_exit="2024-12-01T00:00:00Z")
    file = tmp_path / "model.json"
    write(file, model)
    protocol = dict(
        frozen_at="2024-12-31T00:00:00Z",
        models={"price_only-1h": dict(file=str(file), sha256=sha(file))},
    )
    eth = [dict(r, asset="ETHUSDT") for r in source]
    generated = datetime.fromisoformat(source[-1]["interval_end"]) + timedelta(
        minutes=5
    )
    result = forecast_capture(
        {"prices": {"BTCUSDT": source, "ETHUSDT": eth}}, protocol, generated.isoformat()
    )
    assert len(result["forecasts"]) == 2
    assert all(
        datetime.fromisoformat(r["entry_at"]) > generated for r in result["forecasts"]
    )
    late = forecast_capture(
        {"prices": {"BTCUSDT": source, "ETHUSDT": eth}},
        protocol,
        (generated + timedelta(hours=1)).isoformat(),
    )
    assert late["forecasts"] == [] and len(late["blocked"]) == 2


def test_forecast_cli_cannot_write_into_sealed_protocol(tmp_path, monkeypatch):
    import sys
    from crypto_mm.intraday.cli import main
    from crypto_mm.intraday.inputs import write, sha, seal

    folder = tmp_path / "protocol"
    folder.mkdir()
    write(folder / "protocol.json", {"models": {}})
    seal(folder)
    capture = tmp_path / "capture.json"
    write(capture, {"prices": {}})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli",
            "forecast",
            "--capture",
            str(capture),
            "--capture-sha256",
            sha(capture),
            "--protocol",
            str(folder / "protocol.json"),
            "--output",
            str(folder / "extra.json"),
            "--generated-at",
            "2026-11-07T12:00:00Z",
        ],
    )
    with pytest.raises(ValueError):
        main()
    assert not (folder / "extra.json").exists()


def test_frozen_forecaster_rejects_wrong_feature_order(tmp_path):
    from crypto_mm.intraday.forecast import forecast_capture
    from crypto_mm.intraday.features import NAMES
    from crypto_mm.intraday.inputs import write, sha

    model = dict(
        schema="crypto.ridge_checkpoint.v1",
        features=list(reversed(NAMES)),
        x_mean=[0.0] * 7,
        x_scale=[1.0] * 7,
        y_mean=0.0,
        y_scale=1.0,
        coef=[0.0] * 7,
        intercept=0.0,
        step_hours=1,
        arm="price_only",
        fit_last_exit="2024-12-01T00:00:00Z",
    )
    file = tmp_path / "model.json"
    write(file, model)
    source = bars(400)
    protocol = dict(
        frozen_at="2024-12-31T00:00:00Z",
        models={"price_only-1h": dict(file=str(file), sha256=sha(file))},
    )
    generated = (
        datetime.fromisoformat(source[-1]["interval_end"]) + timedelta(minutes=5)
    ).isoformat()
    with pytest.raises(ValueError):
        forecast_capture(
            {
                "prices": {
                    "BTCUSDT": source,
                    "ETHUSDT": [dict(r, asset="ETHUSDT") for r in source],
                }
            },
            protocol,
            generated,
        )
