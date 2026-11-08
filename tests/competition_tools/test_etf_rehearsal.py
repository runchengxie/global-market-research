"""Retrospective proxy arithmetic and strict chart/mark boundaries."""

from datetime import datetime, timezone
from decimal import Decimal
import pytest


def chart(
    symbol="USMV",
    currency="USD",
    timestamps=None,
    opens=None,
    closes=None,
    adjusted=None,
):
    return {
        "chart": {
            "error": None,
            "result": [
                {
                    "meta": {
                        "symbol": symbol,
                        "currency": currency,
                        "exchangeTimezoneName": "America/New_York",
                    },
                    "timestamp": timestamps
                    or [
                        int(
                            datetime(
                                2026, 1, 2, 14, 30, tzinfo=timezone.utc
                            ).timestamp()
                        )
                    ],
                    "indicators": {
                        "quote": [{"open": opens or [100], "close": closes or [100]}],
                        "adjclose": [{"adjclose": adjusted or [90]}],
                    },
                }
            ],
        }
    }


def test_shared_arithmetic_preserves_shadow_example_and_empty_risk_off():
    from competition_tools.competition_review.shadow import interval_arithmetic

    r = interval_arithmetic({"1": ".5"}, {"1": ".6"}, {"1": ".1"}, ".01", ".02", "10")
    assert Decimal(r["target_return_after_initial_cost"]) == Decimal(".0639")
    off = interval_arithmetic({"1": ".5"}, {}, {"1": ".1"}, "0", "0", "10")
    assert Decimal(off["target_return_after_initial_cost"]) == Decimal("-.0005")
    with pytest.raises(ValueError):
        interval_arithmetic({"1": "1.1"}, {}, {"1": ".1"}, "0", "0", "10")


def test_parser_uses_adjusted_units_and_records_outside_requested_quote():
    from competition_tools.competition_review.etf_rehearsal import parse_chart

    raw = chart(
        timestamps=[
            int(datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc).timestamp()),
            int(datetime(2026, 11, 8, tzinfo=timezone.utc).timestamp()),
        ],
        opens=[100, 200],
        closes=[100, 200],
        adjusted=[90, 180],
    )
    rows, issues = parse_chart(raw, "USMV", "USD", "2023-01-01", "2026-11-07")
    assert rows[0]["adjusted_open"] == Decimal("90")
    assert len(rows) == 1 and issues["outside_requested_range"] == 1


@pytest.mark.parametrize(
    "mode",
    [
        "wrong_symbol",
        "wrong_currency",
        "array_mismatch",
        "nonfinite",
        "duplicate",
        "null",
    ],
)
def test_chart_invalid_data_cannot_be_silently_used(mode):
    from competition_tools.competition_review.etf_rehearsal import parse_chart

    raw = chart()
    item = raw["chart"]["result"][0]
    if mode == "wrong_symbol":
        item["meta"]["symbol"] = "OTHER"
    elif mode == "wrong_currency":
        item["meta"]["currency"] = "EUR"
    elif mode == "array_mismatch":
        item["indicators"]["quote"][0]["open"] = [1, 2]
    elif mode == "nonfinite":
        item["indicators"]["quote"][0]["open"] = ["NaN"]
    elif mode == "duplicate":
        item["timestamp"] *= 2
        item["indicators"]["quote"][0]["open"] *= 2
        item["indicators"]["quote"][0]["close"] *= 2
        item["indicators"]["adjclose"][0]["adjclose"] *= 2
    else:
        item["indicators"]["quote"][0]["open"] = [None]
        with pytest.raises(ValueError):
            parse_chart(raw, "USMV", "USD", "2023-01-01", "2026-11-07")
        return
    with pytest.raises(ValueError):
        parse_chart(raw, "USMV", "USD", "2023-01-01", "2026-11-07")


def test_asof_marks_never_take_future_or_stale_and_fx_direction():
    from competition_tools.competition_review.etf_rehearsal import asof_mark, base_mark

    rows = [
        {"at": datetime(2026, 1, 2, tzinfo=timezone.utc), "value": Decimal("2")},
        {"at": datetime(2026, 1, 3, tzinfo=timezone.utc), "value": Decimal("99")},
    ]
    assert asof_mark(rows, datetime(2026, 1, 2, 14, tzinfo=timezone.utc))["value"] == 2
    with pytest.raises(ValueError):
        asof_mark(rows, datetime(2026, 1, 7, tzinfo=timezone.utc))
    assert base_mark(Decimal("100"), "JPY", Decimal("1.3"), Decimal("130")) == 1
    assert base_mark(Decimal("100"), "USD", Decimal("1.3"), Decimal("130")) == 130


def test_sma_requires_exact_200_completed_sessions_and_strict_above():
    from competition_tools.competition_review.etf_rehearsal import sma_signal

    days = [str(n) for n in range(200)]
    prices = {day: Decimal("100") for day in days}
    assert sma_signal(prices, days) is False
    prices[days[-1]] = Decimal("101")
    assert sma_signal(prices, days) is True
    prices.pop(days[0])
    with pytest.raises(ValueError):
        sma_signal(prices, days)


def test_nonflat_rehearsal_funding_endpoint_reconstruction_and_tamper(tmp_path):
    import json
    import exchange_calendars as xc
    from test_strategy_case import RAW
    from competition_tools.crypto_evidence import digest, seal, verify_seal
    from competition_tools.competition_review.flex_reconciliation import (
        reconcile_snapshot,
    )
    from competition_tools.competition_review.etf_rehearsal import run

    source = tmp_path / "source"
    source.mkdir()
    records = []
    refs = {}
    us = xc.get_calendar("XNYS", start="2023-01-01", end="2026-11-07").schedule
    jp = xc.get_calendar("XTKS", start="2023-01-01", end="2026-11-07").schedule
    for key, symbol, currency, zone, cal, value in [
        ("usmv", "USMV", "USD", "America/New_York", us, 100),
        ("japan", "1321.T", "JPY", "Asia/Tokyo", jp, 100),
        ("usdsgd", "SGD=X", "SGD", "UTC", us, 1.3),
        ("usdjpy", "JPY=X", "JPY", "UTC", us, 130),
    ]:
        stamps = [
            int(
                (
                    r["open"] if key in ["usmv", "japan"] else t.tz_localize("UTC")
                ).timestamp()
            )
            for t, r in cal.iterrows()
        ]
        payload = chart(
            symbol,
            currency,
            stamps,
            [value + i / 10 for i in range(len(stamps))]
            if key == "usmv"
            else [value] * len(stamps),
            [value] * len(stamps),
            [value] * len(stamps),
        )
        payload["chart"]["result"][0]["meta"]["exchangeTimezoneName"] = zone
        p = source / (key + ".json")
        p.write_text(json.dumps(payload))
        sha = digest(p)
        records.append(
            dict(
                symbol=symbol,
                status="received",
                sha256=sha,
                requested_start="2023-01-01",
                requested_end_exclusive="2026-11-07",
            )
        )
        refs[key] = dict(path=str(p), sha256=sha)
    (source / "receipt.json").write_text(json.dumps(dict(records=records)))
    seal(source)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    raw = (
        RAW.replace(b'currency="USD"', b'currency="SGD"')
        .replace(b'symbol="A"', b'symbol="USMV"')
        .replace(b'position="50"', b'position="40"')
        .replace(b'positionValue="50"', b'positionValue="40"')
        .replace(
            b'currency="SGD" assetCategory="STK"', b'currency="USD" assetCategory="STK"'
        )
    )
    row = b'<OpenPosition accountId="SYNTH" currency="JPY" assetCategory="STK" symbol="1321.T" conid="2" reportDate="20261106" position="10" markPrice="100" positionValue="1000" multiplier="1" fxRateToBase="0.01" levelOfDetail="SUMMARY"/>'
    raw = raw.replace(b"</OpenPositions>", row + b"</OpenPositions>")
    (snapshot / "report.xml").write_bytes(raw)
    (snapshot / "snapshot.json").write_text(
        json.dumps(
            reconcile_snapshot(
                raw, expected_account="SYNTH", base_currency="SGD", account_ref="paper"
            )
        )
    )
    (snapshot / "receipt.json").write_text(
        json.dumps(
            dict(
                status="collected",
                account_ref="paper",
                report_sha256=digest(snapshot / "report.xml"),
                finished_at="2026-11-07T00:00:00Z",
            )
        )
    )
    seal(snapshot)
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
    out = tmp_path / "result"
    result = run(manifest, snapshot, out)
    verify_seal(out)
    assert len(result["cases"]) == 27 and result["accepted_research"] is False
    assert all(set(w["asset_return_proxies"]) == {"1", "2"} for w in result["windows"])
    fixed = next(
        c
        for c in result["cases"]
        if c["candidate"] == "fixed_half" and c["one_way_cost_bps"] == "10"
    )
    entry_index = list(us.index.date).index(datetime(2026, 4, 2).date())
    exit_index = list(us.index.date).index(datetime(2026, 5, 1).date())
    entry_open = Decimal(str(100 + entry_index / 10))
    exit_open = Decimal(str(100 + exit_index / 10))
    independent_endpoint = Decimal(".5") * exit_open / entry_open + Decimal(".4998")
    assert abs(
        Decimal(fixed["target_return_after_initial_cost"]) - (independent_endpoint - 1)
    ) < Decimal("1e-24")
    assert fixed["initial_cash_after_cost"] == "0.4998"
    assert abs(Decimal(fixed["endpoint_reconstruction_residual"])) < Decimal("1e-24")
    for window in result["windows"]:
        for mark in window["endpoint_marks"]:
            assert all(
                Decimal(v) <= 72 for v in mark["modeled_mark_age_hours"].values()
            )
    daily = run(manifest, snapshot, tmp_path / "daily", daily_paths=True)
    assert daily["schema"] == "competition.etf_rehearsal.v2"
    complete = [w for w in daily["windows"] if not w["daily_path_blockers"]]
    assert len(complete) == 1 and all(len(w["daily_marks"]) == 21 for w in complete)
    july = next(w for w in daily["windows"] if w["cutoff"] == "2026-07-01")
    assert july["daily_path_status"] == "blocked_missing_or_stale_mark"
    assert any(
        b["session_date"] == "2026-07-20" and b["reason"] == "STALE_MARK"
        for b in july["daily_path_blockers"]
    )
    for c in daily["cases"]:
        if c["cutoff"] != "2026-04-01":
            assert c["cash_scenarios"] is None
            continue
        assert len(c["cash_scenarios"]) == 3
        zero = c["cash_scenarios"][0]
        assert abs(
            Decimal(zero["return_after_initial_cost"])
            - Decimal(c["target_return_after_initial_cost"])
        ) < Decimal("1e-24")
        assert len(zero["path"]) == 21
    assert result["schema"] == "competition.etf_rehearsal.v1"
    assert "cash_scenarios" not in result["cases"][0]
    with pytest.raises(FileExistsError):
        run(manifest, snapshot, out)
    (source / "usmv.json").write_text("{}")
    with pytest.raises(ValueError):
        run(manifest, snapshot, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
