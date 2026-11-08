"""Synthetic sealed sources/protocol and causal adapter coverage."""

from datetime import datetime, timezone
import json
import math
import pytest
from competition_tools.crypto_evidence import digest, seal, verify_seal

NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)


@pytest.fixture
def study(tmp_path):
    import exchange_calendars as xc
    from competition_tools.competition_review.etf_rehearsal import SOURCES

    cal = xc.get_calendar("XNYS", start="2023-01-01", end="2026-11-06").schedule
    source = tmp_path / "source"
    source.mkdir()
    refs = {}
    records = []
    for key, (symbol, currency) in SOURCES.items():
        values = [
            100 + i * 0.02 + 2 * math.sin(i / 9) + math.sin(i / 27)
            for i in range(len(cal))
        ]
        payload = dict(
            chart=dict(
                error=None,
                result=[
                    dict(
                        meta=dict(
                            symbol=symbol,
                            currency=currency,
                            exchangeTimezoneName="America/New_York",
                        ),
                        timestamp=[
                            int(row["open"].timestamp()) for _, row in cal.iterrows()
                        ],
                        indicators=dict(
                            quote=[dict(open=values, close=values)],
                            adjclose=[dict(adjclose=values)],
                        ),
                    )
                ],
            )
        )
        p = source / (key + ".json")
        p.write_text(json.dumps(payload))
        refs[key] = dict(path=str(p), sha256=digest(p))
        records.append(
            dict(
                symbol=symbol,
                status="received",
                sha256=digest(p),
                requested_start="2023-01-01",
                requested_end_exclusive="2026-11-07",
                requested_at="2026-11-07T00:00:00Z",
                finished_at="2026-11-07T00:01:00Z",
            )
        )
    (source / "receipt.json").write_text(json.dumps(dict(records=records)))
    seal(source)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    manifest = inputs / "manifest.json"
    manifest.write_text(
        json.dumps(
            dict(
                schema="competition.etf_rehearsal_inputs.v1",
                sources=refs,
                core_conid="1",
                japan_conid="2",
            )
        )
    )
    seal(inputs)
    root = tmp_path / "protocol"
    root.mkdir()
    protocol = dict(
        schema="competition.volatility_study_protocol.v1",
        frozen_at="2026-11-08T00:00:00Z",
        manifest_sha256=digest(manifest),
        symbol="USMV",
        currency="USD",
        calibration_start="2024-01-02",
        calibration_end="2024-12-31",
        evaluation_start="2025-01-02",
        evaluation_end="2026-11-06",
        lookback_returns=20,
        annualization=252,
        target_volatility=0.05,
        cap=1.0,
        fixed_reference_weight=0.5,
        one_way_cost_bps=[0, 10, 25],
        buffer_sensitivity=0.05,
        cash_return=0,
        leverage_allowed=False,
        parameter_optimization=False,
        execution_authorized=False,
        match_tolerance=1e-7,
    )
    (root / "protocol.json").write_text(json.dumps(protocol))
    seal(root)
    return manifest, root, protocol


def test_all_arms_costs_and_hindsight_control_remain_diagnostics(study, tmp_path):
    from competition_tools.competition_review.volatility_study import run

    m, p, _ = study
    r = run(m, p, tmp_path / "result", now=NOW)
    assert len(r["cases"]) == 15
    assert r["accepted_research"] is False and r["execution_authorized"] is False
    assert r["currency"] == "USD" and r["actual_account_performance"] is False
    assert r["calibration"]["end"] < "2025-01-02"
    assert all(
        abs(c["match_residual"]) <= 1e-7
        for c in r["cases"]
        if c["arm"] == "hindsight_exposure_matched"
    )
    assert all(
        c["hindsight_nontradable"]
        for c in r["cases"]
        if c["arm"] == "hindsight_exposure_matched"
    )
    assert all(c["result"]["path"][-1]["stock_value"] == 0 for c in r["cases"])
    verify_seal(tmp_path / "result")
    with pytest.raises(FileExistsError):
        run(m, p, tmp_path / "result", now=NOW)


@pytest.mark.parametrize(
    "mode",
    [
        "overlap",
        "future_freeze",
        "wrong_hash",
        "wrong_currency",
        "bad_target",
        "missing_source",
    ],
)
def test_invalid_protocol_or_source_creates_no_output(study, tmp_path, mode):
    from competition_tools.competition_review.volatility_study import run

    m, p, raw = study
    if mode == "overlap":
        raw["calibration_end"] = raw["evaluation_start"]
    elif mode == "future_freeze":
        raw["frozen_at"] = "2027-01-01T00:00:00Z"
    elif mode == "wrong_hash":
        raw["manifest_sha256"] = "a" * 64
    elif mode == "wrong_currency":
        raw["currency"] = "SGD"
    elif mode == "bad_target":
        raw["target_volatility"] = 0
    elif mode == "missing_source":
        (m.parent.parent / "source/usmv.json").write_text("{}")
    (p / "protocol.json").write_text(json.dumps(raw))
    (p / "seal.json").unlink()
    seal(p)
    with pytest.raises(ValueError):
        run(m, p, tmp_path / "bad", now=NOW)
    assert not (tmp_path / "bad").exists()


def test_current_or_future_close_cannot_change_initial_target(study):
    from competition_tools.competition_review.volatility_study import prepare_points
    from competition_tools.competition_review.etf_rehearsal import _inputs

    _, data, _ = _inputs(study[0])
    raw = study[2]
    a = prepare_points(
        data["usmv"], raw, raw["evaluation_start"], raw["evaluation_end"]
    )
    changed = [dict(r) for r in data["usmv"]]
    for r in changed:
        if r["date"] >= raw["evaluation_start"]:
            r["adjusted_close"] *= 2
    b = prepare_points(changed, raw, raw["evaluation_start"], raw["evaluation_end"])
    assert a[0]["target"] == b[0]["target"]
    assert a[0]["window_end_date"] < "2025-01-02"
    assert a[0]["signal_at"] < a[0]["at"]
    missing = [r for r in data["usmv"] if r["date"] != "2025-01-03"]
    with pytest.raises(ValueError):
        prepare_points(missing, raw, raw["evaluation_start"], raw["evaluation_end"])
