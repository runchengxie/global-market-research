"""Retrospective adjusted-unit/as-of-mark calculations; no trading or data service."""

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, DecimalException
from pathlib import Path
from zoneinfo import ZoneInfo

from competition_tools.crypto_evidence import read_json, digest, verify_seal
from competition_tools.datasets.daily_storage import safe_path
from .shadow import interval_arithmetic, _save
from .strategy_case import _snapshot
from .evidence import aware

SOURCES = {
    "usmv": ("USMV", "USD"),
    "japan": ("1321.T", "JPY"),
    "usdsgd": ("SGD=X", "SGD"),
    "usdjpy": ("JPY=X", "JPY"),
}
CUTOFFS = ("2026-04-01", "2026-07-01", "2026-10-01")


def positive(value):
    if type(value) not in (str, int, float, Decimal):
        raise ValueError("INVALID_PRICE")
    n = Decimal(str(value))
    if not n.is_finite() or n <= 0:
        raise ValueError("INVALID_PRICE")
    return n


def parse_chart(payload, symbol, currency, start, end):
    chart = payload["chart"]
    if chart["error"] or len(chart["result"]) != 1:
        raise ValueError("CHART_ERROR")
    item = chart["result"][0]
    meta = item["meta"]
    if meta["symbol"] != symbol or meta["currency"] != currency:
        raise ValueError("SOURCE_IDENTITY_MISMATCH")
    zone = ZoneInfo(meta["exchangeTimezoneName"])
    stamps = item["timestamp"]
    quote = item["indicators"]["quote"][0]
    adjusted = item["indicators"]["adjclose"][0]["adjclose"]
    if any(len(x) != len(stamps) for x in [quote["open"], quote["close"], adjusted]):
        raise ValueError("CHART_ARRAY_LENGTH")
    rows = []
    seen = set()
    issues = dict(outside_requested_range=0, null_rows=0)
    previous = None
    for i, stamp in enumerate(stamps):
        if type(stamp) is not int:
            raise ValueError("INVALID_EVENT_TIMESTAMP")
        at = datetime.fromtimestamp(stamp, timezone.utc)
        day = at.astimezone(zone).date().isoformat()
        if not start <= day < end:
            issues["outside_requested_range"] += 1
            continue
        if day in seen or (previous and at <= previous):
            raise ValueError("DUPLICATE_OR_UNORDERED_SOURCE")
        seen.add(day)
        previous = at
        values = [quote["open"][i], quote["close"][i], adjusted[i]]
        if any(x is None for x in values):
            issues["null_rows"] += 1
            continue
        opening, closing, adj = map(positive, values)
        rows.append(
            dict(
                date=day,
                event_at=at,
                open=opening,
                close=closing,
                adjusted_close=adj,
                adjusted_open=opening * adj / closing,
            )
        )
    if not rows:
        raise ValueError("EMPTY_USABLE_CHART")
    return rows, issues


def asof_mark(rows, at):
    eligible = [r for r in rows if r["at"] <= at]
    if not eligible:
        raise ValueError("NO_PRIOR_MARK")
    row = max(eligible, key=lambda r: r["at"])
    if at - row["at"] > timedelta(hours=72):
        raise ValueError("STALE_MARK")
    return row


def base_mark(value, currency, sgd_per_usd, jpy_per_usd):
    if currency == "USD":
        return positive(value) * positive(sgd_per_usd)
    if currency == "JPY":
        return positive(value) * positive(sgd_per_usd) / positive(jpy_per_usd)
    raise ValueError("UNSUPPORTED_MARK_CURRENCY")


def sma_signal(prices, days):
    if len(days) != 200 or len(set(days)) != 200 or any(d not in prices for d in days):
        raise ValueError("EXACT_200_SESSIONS_REQUIRED")
    values = [positive(prices[d]) for d in days]
    return values[-1] > sum(values) / 200


def _inputs(manifest_file):
    path = safe_path(Path(manifest_file))
    verify_seal(path.parent)
    m = read_json(path)
    if m["schema"] != "competition.etf_rehearsal_inputs.v1" or set(m["sources"]) != set(
        SOURCES
    ):
        raise ValueError("INVALID_REHEARSAL_MANIFEST")
    data = {}
    issues = {}
    for key, (symbol, currency) in SOURCES.items():
        r = m["sources"][key]
        p = safe_path(Path(r["path"]))
        verify_seal(p.parent)
        receipt = read_json(p.parent / "receipt.json")
        records = [
            v
            for v in receipt["records"]
            if v["symbol"] == symbol and v["status"] == "received"
        ]
        if (
            len(records) != 1
            or records[0]["sha256"] != r["sha256"]
            or digest(p) != r["sha256"]
        ):
            raise ValueError("SOURCE_HASH_OR_RECEIPT_MISMATCH")
        rec = records[0]
        data[key], issues[key] = parse_chart(
            read_json(p),
            symbol,
            currency,
            rec["requested_start"],
            rec["requested_end_exclusive"],
        )
    return m, data, issues


def run(manifest_file, snapshot_root, output):
    try:
        return _run(manifest_file, snapshot_root, output)
    except (KeyError, TypeError, DecimalException, OverflowError) as exc:
        raise ValueError("INVALID_ETF_REHEARSAL") from exc


def _run(manifest_file, snapshot_root, output):
    import exchange_calendars as xc
    from importlib.metadata import version

    manifest, data, issues = _inputs(manifest_file)
    snapshot, reference, _ = _snapshot(Path(snapshot_root), datetime.now(timezone.utc))
    if snapshot["base_currency"] != "SGD":
        raise ValueError("SGD_REFERENCE_REQUIRED")
    identities = {
        p["conid"]: (p["symbol"], p["currency"]) for p in snapshot["stock"]["positions"]
    }
    core = manifest["core_conid"]
    jp = manifest["japan_conid"]
    if core == jp or identities != {core: ("USMV", "USD"), jp: ("1321.T", "JPY")}:
        raise ValueError("FULL_REFERENCE_IDENTITY_REQUIRED")
    us = xc.get_calendar("XNYS", start="2023-01-01", end="2026-11-07").schedule
    japan = xc.get_calendar("XTKS", start="2023-01-01", end="2026-11-07").schedule
    us_rows = {
        t.date().isoformat(): dict(
            open=aware(r["open"].isoformat()), close=aware(r["close"].isoformat())
        )
        for t, r in us.iterrows()
    }
    jp_rows = {
        t.date().isoformat(): dict(
            open=aware(r["open"].isoformat()), close=aware(r["close"].isoformat())
        )
        for t, r in japan.iterrows()
    }
    for key, calendar in [("usmv", us_rows), ("japan", jp_rows)]:
        for r in data[key]:
            if (
                r["date"] not in calendar
                or r["event_at"] != calendar[r["date"]]["open"]
            ):
                raise ValueError("SOURCE_SESSION_CLOCK_MISMATCH")
    core_rows = {r["date"]: r for r in data["usmv"]}
    jp_marks = [
        dict(at=jp_rows[r["date"]]["close"], value=r["adjusted_close"])
        for r in data["japan"]
    ]
    fx = {
        k: [dict(at=r["event_at"], value=r["open"]) for r in data[k]]
        for k in ["usdsgd", "usdjpy"]
    }
    dates = list(us_rows)
    cases = []
    windows = []
    for cutoff in CUTOFFS:
        index = dates.index(cutoff)
        days = dates[index - 199 : index + 1]
        prices = {d: r["close"] for d, r in core_rows.items()}
        signal = sma_signal(prices, days)
        endpoints = [dates[index + 1], dates[index + 21]]
        marks = []
        base_values = []
        for day in endpoints:
            if day not in core_rows:
                raise ValueError("CORE_ENDPOINT_MISSING")
            at = us_rows[day]["open"]
            j = asof_mark(jp_marks, at)
            sgd = asof_mark(fx["usdsgd"], at)
            yen = asof_mark(fx["usdjpy"], at)
            values = {
                core: base_mark(
                    core_rows[day]["adjusted_open"], "USD", sgd["value"], yen["value"]
                ),
                jp: base_mark(j["value"], "JPY", sgd["value"], yen["value"]),
            }
            base_values.append(values)
            marks.append(
                dict(
                    endpoint=at.isoformat(),
                    core_date=day,
                    japan_modeled_close=j["at"].isoformat(),
                    fx_sgd_daily_open=sgd["at"].isoformat(),
                    fx_jpy_daily_open=yen["at"].isoformat(),
                    modeled_mark_age_hours={
                        key: str(Decimal(str((at - row["at"]).total_seconds())) / 3600)
                        for key, row in [("japan", j), ("usdsgd", sgd), ("usdjpy", yen)]
                    },
                    base_values={k: str(v) for k, v in values.items()},
                )
            )
        returns = {k: base_values[1][k] / base_values[0][k] - 1 for k in reference}
        arms = {
            "observed_reference": reference,
            "fixed_half": {core: "0.5"},
            "initial_trend_half": {core: "0.5"} if signal else {},
        }
        benchmark = sum(Decimal(w) * returns[k] for k, w in reference.items())
        for name, weights in arms.items():
            for fee in ["0", "10", "25"]:
                result = interval_arithmetic(
                    reference, weights, returns, "0", benchmark, fee
                )
                residual = 1 - sum((Decimal(v) for v in weights.values()), Decimal(0))
                cash_after_cost = residual - Decimal(result["initial_cost_fraction"])
                if cash_after_cost < 0:
                    raise ValueError("INITIAL_COST_NOT_CASH_FUNDED")
                endpoint_stock = sum(
                    (Decimal(w) * (1 + returns[k]) for k, w in weights.items()),
                    Decimal(0),
                )
                reconstructed = endpoint_stock + cash_after_cost
                error = reconstructed - (
                    1 + Decimal(result["target_return_after_initial_cost"])
                )
                if abs(error) > Decimal("1e-24"):
                    raise ValueError("ENDPOINT_RECONSTRUCTION_FAILED")
                cases.append(
                    dict(
                        cutoff=cutoff,
                        candidate=name,
                        one_way_cost_bps=fee,
                        initial_stock_weights=weights,
                        initial_non_stock_weight=str(residual),
                        initial_cash_after_cost=str(cash_after_cost),
                        endpoint_stock_value=str(endpoint_stock),
                        reconstructed_final_value=str(reconstructed),
                        endpoint_reconstruction_residual=str(error),
                        **result,
                    )
                )
        windows.append(
            dict(
                cutoff=cutoff,
                modeled_signal_at=(
                    us_rows[cutoff]["close"] + timedelta(minutes=30)
                ).isoformat(),
                entry=us_rows[endpoints[0]]["open"].isoformat(),
                exit=us_rows[endpoints[1]]["open"].isoformat(),
                completed_signal_sessions=len(days),
                close=str(prices[cutoff]),
                sma200=str(sum(prices[d] for d in days) / 200),
                initial_trend_risk_on=signal,
                asset_return_proxies={k: str(v) for k, v in returns.items()},
                endpoint_marks=marks,
            )
        )
    result = dict(
        schema="competition.etf_rehearsal.v1",
        status="retrospective_diagnostic_completed",
        source_manifest_sha256=digest(manifest_file),
        snapshot_sha256=digest(Path(snapshot_root) / "snapshot.json"),
        calendar_package_version=version("exchange-calendars"),
        reference_report_date=snapshot["report_date"],
        input_exclusions=issues,
        windows=windows,
        cases=cases,
        accepted_research=False,
        execution_authorized=False,
        live_readiness=False,
        first_cycle_status="awaiting_initial_future_close_and_reviewed_source_semantics_policy",
        full_real_ledger_gate_changed=False,
        limitations=[
            "Already exposed historical windows and current portfolio selection are hindsight, not out-of-sample strategy evidence.",
            "Vendor-adjusted opening units and as-of Japanese closes/daily FX opens are non-executable proxies; event clocks are modeled, not verified historical publication times.",
            "Do not add dividends again; this is not a certified total-return or cashflow ledger.",
            "Residual zero-return SGD and initial linear costs exclude real multi-currency cash, tax, financing, impact and terminal liquidation.",
            "No daily NAV/drawdown or full accounting replay is inferred from one-interval arithmetic.",
        ],
    )
    text = "\n".join(
        f"{r['cutoff']} {r['candidate']} {r['one_way_cost_bps']}bp: {float(r['target_return_after_initial_cost']) * 100:.4f}%"
        for r in cases
    )
    return _save(
        output,
        "rehearsal.json",
        result,
        [Path(manifest_file).parent, Path(snapshot_root)]
        + [Path(r["path"]).parent for r in manifest["sources"].values()],
        "# Retrospective ETF calculation rehearsal\n\nHistorical engineering diagnostic only; no adoption, broker performance or total-return certification. Current reference holdings are hindsight. Vendor-adjusted units/as-of marks are not executable prices. All27cases follow, with no winner selection.\n\n```text\n"
        + text
        + "\n```\n\nFull marks, exclusions, signals, costs and limitations: rehearsal.json. The future cycle remains pending; no deadline was shifted or first-session record backfilled.",
        "# ETF 历史计算演练\n\n仅为历史工程诊断，不代表采用建议、券商业绩或总收益认证。当前参考持仓属于事后选择；供应方调整单位和时点代理价格不可直接成交。以下保留全部27组结果，不挑赢家。\n\n```text\n"
        + text
        + "\n```\n\n完整价格、排除行、信号、费用和局限见 rehearsal.json。未来周期仍待输入，没有移动截止或补写首日记录。",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    run(a.manifest, a.snapshot, a.output)
    print(
        "Private retrospective diagnostic saved; no research or execution acceptance."
    )


if __name__ == "__main__":
    main()
