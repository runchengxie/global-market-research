"""Retrospective volatility sizing with explicit hindsight exposure controls."""

import argparse
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

from competition_tools.crypto_evidence import digest, read_json, verify_seal
from competition_tools.datasets.daily_storage import safe_path
from .etf_rehearsal import _inputs
from .evidence import aware
from .shadow import _save
from .volatility_math import number, target_from_closes, simulate, match_fixed


def _protocol(root, manifest, now):
    root = safe_path(Path(root))
    verify_seal(root)
    p = read_json(root / "protocol.json")
    if p["schema"] != "competition.volatility_study_protocol.v1" or p[
        "manifest_sha256"
    ] != digest(manifest):
        raise ValueError("PROTOCOL_SOURCE_BINDING_MISMATCH")
    if p["symbol"] != "USMV" or p["currency"] != "USD" or aware(p["frozen_at"]) > now:
        raise ValueError("INVALID_STUDY_IDENTITY_OR_FREEZE")
    dates = [
        p[k]
        for k in [
            "calibration_start",
            "calibration_end",
            "evaluation_start",
            "evaluation_end",
        ]
    ]
    if (
        any(date.fromisoformat(d).isoformat() != d for d in dates)
        or not dates[0] < dates[1] < dates[2] < dates[3]
    ):
        raise ValueError("NONOVERLAPPING_CALIBRATION_EVALUATION_REQUIRED")
    if type(p["lookback_returns"]) is not int or not 2 <= p["lookback_returns"] <= 252:
        raise ValueError("INVALID_VOL_WINDOW")
    if type(p["annualization"]) is not int or not 1 <= p["annualization"] <= 366:
        raise ValueError("INVALID_ANNUALIZATION")
    number(p["target_volatility"], high=1, positive=True)
    number(p["fixed_reference_weight"], high=1)
    number(p["buffer_sensitivity"], high=1, positive=True)
    number(p["match_tolerance"], high=1e-4, positive=True)
    if (
        number(p["cap"], high=1) != 1
        or number(p["cash_return"], high=0) != 0
        or any(
            p[k] is not False
            for k in [
                "leverage_allowed",
                "parameter_optimization",
                "execution_authorized",
            ]
        )
    ):
        raise ValueError("UNLEVERED_ZERO_CASH_DIAGNOSTIC_REQUIRED")
    costs = p["one_way_cost_bps"]
    if not isinstance(costs, list) or not 1 <= len(costs) <= 8:
        raise ValueError("INVALID_COST_SCENARIOS")
    for cost in costs:
        number(cost, high=100)
    if costs != sorted(set(costs)):
        raise ValueError("ORDERED_UNIQUE_COST_SCENARIOS_REQUIRED")
    return root, p


def prepare_points(data, protocol, start, end):
    import exchange_calendars as xc

    lookup = {r["date"]: r for r in data}
    if len(lookup) != len(data) or not lookup:
        raise ValueError("DUPLICATE_OR_EMPTY_STUDY_DATA")
    calendar = xc.get_calendar("XNYS", start=min(lookup), end=max(lookup)).schedule
    schedule = {label.date().isoformat(): row for label, row in calendar.iterrows()}
    if set(lookup) != set(schedule) or start not in lookup or end not in lookup:
        raise ValueError("COMPLETE_EXACT_XNYS_HISTORY_REQUIRED")
    dates = list(schedule)
    for day, row in lookup.items():
        if aware(row["event_at"].isoformat()) != aware(
            schedule[day]["open"].isoformat()
        ):
            raise ValueError("STUDY_DAILY_CLOCK_MISMATCH")
        number(float(row["adjusted_open"]), positive=True)
        number(float(row["adjusted_close"]), positive=True)
    closes = [float(lookup[d]["adjusted_close"]) for d in dates]
    points = []
    n = protocol["lookback_returns"]
    for i, day in enumerate(dates):
        if not start <= day <= end:
            continue
        if i < n + 1:
            raise ValueError("INSUFFICIENT_PRIOR_COMPLETED_CLOSES")
        target = target_from_closes(
            closes[i - n - 1 : i],
            n,
            protocol["target_volatility"],
            protocol["cap"],
            protocol["annualization"],
        )
        at = aware(schedule[day]["open"].isoformat())
        signal = aware(schedule[dates[i - 1]]["close"].isoformat()) + timedelta(
            minutes=30
        )
        if signal >= at:
            raise ValueError("NONCAUSAL_STUDY_SCHEDULE")
        points.append(
            dict(
                date=day,
                at=at.isoformat(),
                signal_at=signal.isoformat(),
                price=float(lookup[day]["adjusted_open"]),
                target=target["weight"],
                estimated_volatility=target["estimated_volatility"],
                window_start_date=dates[i - n - 1],
                window_end_date=dates[i - 1],
                return_observations=n,
                rebalance=day[:7] != dates[i - 1][:7],
            )
        )
    if len(points) < 3:
        raise ValueError("INSUFFICIENT_STUDY_INTERVALS")
    return points


def run(manifest_file, protocol_root, output, *, now=None):
    try:
        return _run(manifest_file, protocol_root, output, now=now)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as exc:
        raise ValueError("MALFORMED_VOLATILITY_STUDY") from exc


def _run(manifest_file, protocol_root, output, *, now=None):
    stamp = aware((now or datetime.now(timezone.utc)).isoformat())
    manifest_file = safe_path(Path(manifest_file))
    protocol_root, p = _protocol(protocol_root, manifest_file, stamp)
    manifest, data, exclusions = _inputs(manifest_file)
    usmv_path = Path(manifest["sources"]["usmv"]["path"])
    receipt = read_json(usmv_path.parent / "receipt.json")
    received = [
        r
        for r in receipt["records"]
        if r["symbol"] == "USMV" and r["status"] == "received"
    ][0]
    if (
        not aware(received["requested_at"])
        <= aware(received["finished_at"])
        <= aware(p["frozen_at"])
    ):
        raise ValueError("SOURCE_MUST_PRECEDE_RETROSPECTIVE_PROTOCOL_FREEZE")
    calibration_points = prepare_points(
        data["usmv"], p, p["calibration_start"], p["calibration_end"]
    )
    points = prepare_points(data["usmv"], p, p["evaluation_start"], p["evaluation_end"])
    if aware(points[-1]["at"]) > aware(received["finished_at"]):
        raise ValueError("SOURCE_PRECEDES_EVALUATION_MARK")
    cal = simulate(calibration_points, 0, annualization=p["annualization"])
    calibrated_weight = cal["metrics"]["mean_exposure"]
    cases = []
    for fee in p["one_way_cost_bps"]:
        vol = simulate(points, fee, annualization=p["annualization"])
        matched = match_fixed(
            points,
            fee,
            vol["metrics"]["mean_exposure"],
            tolerance=p["match_tolerance"],
            annualization=p["annualization"],
        )
        for arm, result, fixed in [
            (
                "fixed_reference",
                simulate(
                    points,
                    fee,
                    fixed_weight=p["fixed_reference_weight"],
                    annualization=p["annualization"],
                ),
                p["fixed_reference_weight"],
            ),
            (
                "calibration_fixed",
                simulate(
                    points,
                    fee,
                    fixed_weight=calibrated_weight,
                    annualization=p["annualization"],
                ),
                calibrated_weight,
            ),
            ("volatility_control", vol, None),
            (
                "buffer_sensitivity",
                simulate(
                    points,
                    fee,
                    buffer=p["buffer_sensitivity"],
                    annualization=p["annualization"],
                ),
                None,
            ),
            ("hindsight_exposure_matched", matched["result"], matched["fixed_weight"]),
        ]:
            cases.append(
                dict(
                    arm=arm,
                    one_way_cost_bps=fee,
                    fixed_weight=fixed,
                    buffer=p["buffer_sensitivity"]
                    if arm == "buffer_sensitivity"
                    else 0,
                    hindsight_nontradable=arm == "hindsight_exposure_matched",
                    match_residual=matched["residual"]
                    if arm == "hindsight_exposure_matched"
                    else None,
                    result=result,
                )
            )
    result = dict(
        schema="competition.volatility_study.v1",
        recorded_at=stamp.isoformat(),
        protocol=p,
        protocol_sha256=digest(protocol_root / "protocol.json"),
        source_manifest_sha256=digest(manifest_file),
        used_source_sha256=manifest["sources"]["usmv"]["sha256"],
        used_source="USMV/USD adjusted unit proxies; other manifest sources verified but not used in this experiment",
        source_exclusions=exclusions["usmv"],
        currency="USD",
        cash_return=0,
        calibration=dict(
            start=p["calibration_start"],
            end=p["calibration_end"],
            fixed_weight=calibrated_weight,
            method="earlier_period_zero_fee_volatility_arm_mean_pre_interval_exposure",
            metrics=cal["metrics"],
        ),
        signal_points=points,
        cases=cases,
        accepted_research=False,
        actual_account_performance=False,
        actual_policy_confirmed=False,
        execution_authorized=False,
        scheduler_installed=False,
        full_real_ledger_gate_changed=False,
        limitations=[
            "Current retrospective experiment, not historical preregistration or independently unseen out-of-sample evidence; vendor adjustments/publication semantics remain unverified.",
            "USD adjusted opening units are non-executable price proxies; cash earns zero, no real dividends/cashflow/FX/financing/tax/spread/impact ledger.",
            "All arms pay entry, scheduled adjustment and terminal liquidation costs; target weights apply to post-fee wealth; hold units between changes.",
            "Hindsight matched fixed weight uses evaluation exposure and is a nontradable diagnostic, not a deployable strategy or causal benchmark.",
            "Mean exposure averages post-trade pre-interval weights; volatility uses open-to-open net intervals with entry fee in the first and exit fee in the last; drawdown anchors pre-cost wealth1.",
            "CAGR/annualized volatility are descriptive annualizations, not forecasts; one ETF/time range and fee/buffer cases are not independent trials or proof of alpha.",
            "Buffer arm changes trade frequency and is a sensitivity only; exact exposure matching applies to the primary zero-buffer arm.",
        ],
    )
    table = "\n".join(
        f"|{c['arm']}|{c['one_way_cost_bps']}|{c['result']['metrics']['total_return'] * 100:.3f}%|{c['result']['metrics']['cagr'] * 100:.3f}%|{c['result']['metrics']['realized_volatility'] * 100:.3f}%|{c['result']['metrics']['maximum_drawdown'] * 100:.3f}%|{c['result']['metrics']['mean_exposure'] * 100:.3f}%|{c['result']['metrics']['sum_trade_turnover']:.4f}|"
        for c in cases
    )
    inputs = [protocol_root, manifest_file.parent] + [
        Path(v["path"]).parent for v in manifest["sources"].values()
    ]
    return _save(
        output,
        "study.json",
        result,
        inputs,
        "# Fixed exposure versus volatility sizing\n\nRetrospective USD adjusted-unit diagnostic only. No actual strategy adoption, account performance or execution authorization. All arms/costs retained; hindsight_exposure_matched is explicitly nontradable. Calibration predates evaluation, but data were acquired retrospectively. Zero cash returns, entry/adjustment/exit fees and monthly constant-unit holdings apply equally; buffer_sensitivity is a separate cadence sensitivity. Risk is measured at opening proxies, not intraday. See study.json for every signal clock, transaction, exposure match residual and limitation.\n\n|Arm|Cost bp|Total return|CAGR|Realized vol|Max drawdown|Mean exposure|Turnover sum|\n|---|---:|---:|---:|---:|---:|---:|---:|\n"
        + table,
        "# 固定配置与波动控制对照\n\n仅为USD调整单位历史诊断，不代表实际策略采用、券商业绩或交易授权。全部方案/费用保留；hindsight_exposure_matched使用评价期平均敞口，是不可实际部署的事后诊断。校准期早于评价期，但行情是事后获取，不能称为独立样本外证据。统一零现金收益和入场/调整/期末清仓费用；月度调整之间固定单位持有。buffer_sensitivity单列调仓缓冲敏感性。风险基于开盘估值代理，不能反映盘中风险。完整信号时点、流水、匹配残差与局限见study.json。\n\n|方案|单边费用bp|累计收益|年化收益|年化实际波动|最大回撤|平均股票敞口|换手合计|\n|---|---:|---:|---:|---:|---:|---:|---:|\n"
        + table,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.manifest, args.protocol, args.output)
    print("Retrospective sizing diagnostic saved; no strategy or execution acceptance.")


if __name__ == "__main__":
    main()
