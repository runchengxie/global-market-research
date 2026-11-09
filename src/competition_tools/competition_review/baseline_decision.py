"""Retrospective common-ledger baselines with explicit unavailable-model rows."""

import argparse
from datetime import date, datetime, timedelta, timezone
import math
from pathlib import Path

from competition_tools.crypto_evidence import digest, read_json, verify_seal
from competition_tools.datasets.daily_storage import safe_path
from .etf_rehearsal import _inputs
from .evidence import aware
from .shadow import _save
from .volatility_math import number, simulate

ARMS = (
    "cash",
    "buy_hold",
    "partial_hold",
    "fixed_monthly",
    "sma_monthly",
    "declared_ranker",
)


def points_for_arm(rows, start, end, arm, *, lookback, weight):
    if arm not in ARMS[:-1]:
        raise ValueError("UNKNOWN_CALCULABLE_BASELINE")
    if type(lookback) is not int or not 2 <= lookback <= 252 or start < lookback:
        raise ValueError("INSUFFICIENT_BASELINE_HISTORY")
    weight = number(weight, high=1, positive=True)
    if not 0 <= start < end < len(rows):
        raise ValueError("INVALID_BASELINE_RANGE")
    points = []
    for i in range(start, end + 1):
        history = [number(r["close"], positive=True) for r in rows[i - lookback : i]]
        selected = history[-1] > sum(history) / lookback
        target = 0 if arm == "cash" else 1 if arm == "buy_hold" else weight
        if arm == "sma_monthly" and not selected:
            target = 0
        points.append(
            dict(
                at=rows[i]["at"],
                signal_at=(
                    aware(rows[i - 1]["close_at"]) + timedelta(minutes=30)
                ).isoformat(),
                price=number(rows[i]["price"], positive=True),
                target=target,
                rebalance=arm in ("fixed_monthly", "sma_monthly")
                and rows[i]["date"][:7] != rows[i - 1]["date"][:7],
                history_start=rows[i - lookback]["date"],
                history_end=rows[i - 1]["date"],
            )
        )
    return points


def compare(cases, episodes, fees, tolerance, material, *, numerator=2, denominator=3):
    tolerance = number(tolerance, high=1e-4)
    material = number(material, high=1, positive=True)
    if (
        any(type(v) is not int for v in [numerator, denominator])
        or not 1 <= numerator <= denominator
    ):
        raise ValueError("INVALID_SCREEN_FRACTION")
    index = {(c["episode"], c["arm"], c["fee_bps"]): c for c in cases}
    if len(index) != len(cases):
        raise ValueError("DUPLICATE_BASELINE_CASE")
    pairs, missing = [], []
    for episode in episodes:
        for fee in fees:
            for arm in ARMS:
                if (episode, arm, fee) not in index:
                    missing.append(dict(episode=episode, arm=arm, fee_bps=fee))
            a = index.get((episode, "sma_monthly", fee))
            b = index.get((episode, "fixed_monthly", fee))
            if (
                a is None
                or b is None
                or a["status"] != "completed"
                or b["status"] != "completed"
            ):
                continue
            if type(a["full_year"]) is not bool or a["full_year"] != b["full_year"]:
                raise ValueError("INCONSISTENT_EPISODE_SCOPE")
            am, bm = a["metrics"], b["metrics"]
            if not all(
                math.isfinite(v)
                for m in [am, bm]
                for v in [m["total_return"], m["maximum_drawdown"]]
            ):
                raise ValueError("NONFINITE_COMPARISON_METRIC")
            ret = am["total_return"] - bm["total_return"]
            dd = am["maximum_drawdown"] - bm["maximum_drawdown"]
            pairs.append(
                dict(
                    episode=episode,
                    fee_bps=fee,
                    full_year=a["full_year"],
                    return_gap=ret,
                    drawdown_gap=dd,
                    passes=ret >= -tolerance
                    and dd >= -tolerance
                    and max(ret, dd) >= material,
                )
            )
    screens = []
    for fee in fees:
        if fee <= 0:
            continue
        eligible = [p for p in pairs if p["fee_bps"] == fee and p["full_year"]]
        count = len(eligible)
        screens.append(
            dict(
                fee_bps=fee,
                full_years=count,
                passes=sum(p["passes"] for p in eligible),
                required=(count * numerator + denominator - 1) // denominator
                if count
                else None,
            )
        )
    incomplete = (
        bool(missing)
        or len(pairs) != len(episodes) * len(fees)
        or not screens
        or any(not s["full_years"] for s in screens)
    )
    passed = bool(screens) and all(
        s["required"] is not None and s["passes"] >= s["required"] for s in screens
    )
    return dict(
        pairs=pairs,
        fee_screens=screens,
        missing_cases=missing,
        screen="unknown_incomplete_comparisons"
        if incomplete
        else "historical_screen_pass"
        if passed
        else "historical_screen_fail",
        model_comparison="blocked_missing_declared_model",
        adoption_authorized=False,
    )


def _protocol(root, manifest, now):
    root = safe_path(Path(root))
    verify_seal(root)
    p = read_json(root / "protocol.json")
    if p["schema"] != "competition.baseline_decision_protocol.v1" or p[
        "manifest_sha256"
    ] != digest(manifest):
        raise ValueError("BASELINE_PROTOCOL_BINDING_MISMATCH")
    if (
        p["symbol"] != "USMV"
        or p["currency"] != "USD"
        or p["execution_authorized"] is not False
        or p["history_previously_examined"] is not True
    ):
        raise ValueError("RETROSPECTIVE_USD_BASELINE_REQUIRED")
    if aware(p["frozen_at"]) > now or p["parameter_optimization"] is not False:
        raise ValueError("INVALID_BASELINE_FREEZE_OR_OPTIMIZATION")
    if type(p["sma_lookback"]) is not int or not 2 <= p["sma_lookback"] <= 252:
        raise ValueError("INVALID_BASELINE_LOOKBACK")
    number(p["stock_weight"], high=1, positive=True)
    for name in ["start", "end"]:
        if date.fromisoformat(p[name]).isoformat() != p[name]:
            raise ValueError("CANONICAL_SESSION_DATE_REQUIRED")
    if (
        not p["start"] < p["end"]
        or date.fromisoformat(p["end"]).year - date.fromisoformat(p["start"]).year > 50
    ):
        raise ValueError("INVALID_BASELINE_PERIOD")
    fees = p["one_way_cost_bps"]
    if not isinstance(fees, list) or not 1 <= len(fees) <= 8:
        raise ValueError("INVALID_BASELINE_FEES")
    for fee in fees:
        number(fee, high=100)
    if fees != sorted(set(fees)) or not any(f > 0 for f in fees):
        raise ValueError("POSITIVE_ORDERED_COST_SCENARIOS_REQUIRED")
    number(p["numerical_tolerance"], high=1e-4)
    number(p["material_improvement"], high=1, positive=True)
    a, b = p["required_share_numerator"], p["required_share_denominator"]
    if type(a) is not int or type(b) is not int or not 1 <= a <= b:
        raise ValueError("INVALID_SCREEN_FRACTION")
    revision = p["source_revision"]
    if (
        not isinstance(revision, str)
        or len(revision) != 40
        or any(c not in "0123456789abcdef" for c in revision)
    ):
        raise ValueError("INVALID_SOURCE_REVISION")
    if p["implementation_sha256"] != digest(Path(__file__)):
        raise ValueError("BASELINE_IMPLEMENTATION_CHANGED")
    return root, p


def run(manifest_file, protocol_root, output):
    try:
        return _run(manifest_file, protocol_root, output)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as error:
        raise ValueError("MALFORMED_BASELINE_INPUT") from error


def _run(manifest_file, protocol_root, output):
    import exchange_calendars as xc

    now = datetime.now(timezone.utc)
    if safe_path(Path(output)).exists():
        raise FileExistsError("BASELINE_OUTPUT_ALREADY_EXISTS")
    manifest_file = safe_path(Path(manifest_file))
    protocol_root, protocol = _protocol(protocol_root, manifest_file, now)
    manifest, data, exclusions = _inputs(manifest_file)
    source_path = Path(manifest["sources"]["usmv"]["path"])
    records = read_json(source_path.parent / "receipt.json")["records"]
    rec = next(
        r for r in records if r["symbol"] == "USMV" and r["status"] == "received"
    )
    if (
        not aware(rec["requested_at"])
        <= aware(rec["finished_at"])
        <= aware(protocol["frozen_at"])
        <= now
    ):
        raise ValueError("INVALID_BASELINE_SOURCE_CHRONOLOGY")
    source = data["usmv"]
    schedule = xc.get_calendar(
        "XNYS", start=source[0]["date"], end=source[-1]["date"]
    ).schedule
    if [r["date"] for r in source] != [d.date().isoformat() for d in schedule.index]:
        raise ValueError("COMPLETE_EXACT_XNYS_HISTORY_REQUIRED")
    rows = []
    for item, (_, clock) in zip(source, schedule.iterrows(), strict=True):
        if item["event_at"] != clock["open"].to_pydatetime():
            raise ValueError("BASELINE_OPEN_CLOCK_MISMATCH")
        rows.append(
            dict(
                date=item["date"],
                at=clock["open"].isoformat(),
                close_at=clock["close"].isoformat(),
                price=number(float(item["adjusted_open"]), positive=True),
                close=number(float(item["adjusted_close"]), positive=True),
            )
        )
    dates = [r["date"] for r in rows]
    if protocol["start"] not in dates or protocol["end"] not in dates:
        raise ValueError("BASELINE_ENDPOINT_MISSING")
    if aware(rows[dates.index(protocol["end"])]["at"]) > aware(rec["finished_at"]):
        raise ValueError("BASELINE_SOURCE_PRECEDES_MARK")
    complete_schedule = xc.get_calendar(
        "XNYS",
        start=protocol["start"][:4] + "-01-01",
        end=protocol["end"][:4] + "-12-31",
    ).schedule
    episodes, cases, point_sets = [], [], []
    for year in range(int(protocol["start"][:4]), int(protocol["end"][:4]) + 1):
        chosen = [
            i
            for i, d in enumerate(dates)
            if protocol["start"] <= d <= protocol["end"] and int(d[:4]) == year
        ]
        if len(chosen) < 2:
            raise ValueError("INSUFFICIENT_ANNUAL_MARKS")
        yearly = [
            d.date().isoformat() for d in complete_schedule.index if d.year == year
        ]
        full = dates[chosen[0]] == yearly[0] and dates[chosen[-1]] == yearly[-1]
        episode = str(year)
        episodes.append(
            dict(
                id=episode,
                start=dates[chosen[0]],
                end=dates[chosen[-1]],
                full_year=full,
                previously_examined=True,
            )
        )
        for arm in ARMS:
            points = (
                None
                if arm == "declared_ranker"
                else points_for_arm(
                    rows,
                    chosen[0],
                    chosen[-1],
                    arm,
                    lookback=protocol["sma_lookback"],
                    weight=protocol["stock_weight"],
                )
            )
            if points is not None:
                point_sets.append(dict(episode=episode, arm=arm, points=points))
            for fee in protocol["one_way_cost_bps"]:
                result = None if points is None else simulate(points, fee)
                cases.append(
                    dict(
                        episode=episode,
                        full_year=full,
                        arm=arm,
                        fee_bps=fee,
                        status="unavailable" if result is None else "completed",
                        reason="DECLARATION_BOUND_MODEL_NOT_SUPPLIED"
                        if result is None
                        else None,
                        metrics=None if result is None else result["metrics"],
                        result=result,
                    )
                )
    comparison = compare(
        cases,
        [e["id"] for e in episodes],
        protocol["one_way_cost_bps"],
        protocol["numerical_tolerance"],
        protocol["material_improvement"],
        numerator=protocol["required_share_numerator"],
        denominator=protocol["required_share_denominator"],
    )
    value = dict(
        schema="competition.baseline_decision.v1",
        recorded_at=now.isoformat(),
        protocol=protocol,
        protocol_sha256=digest(protocol_root / "protocol.json"),
        source_manifest_sha256=digest(manifest_file),
        source_revision=protocol["source_revision"],
        implementation_sha256=protocol["implementation_sha256"],
        used_source_sha256=manifest["sources"]["usmv"]["sha256"],
        source_exclusions=exclusions["usmv"],
        episodes=episodes,
        signal_points=point_sets,
        cases=cases,
        comparison=comparison,
        requested_cases=len(cases),
        completed_cases=sum(c["status"] == "completed" for c in cases),
        unavailable_cases=sum(c["status"] == "unavailable" for c in cases),
        accepted_research=False,
        execution_authorized=False,
        scheduler_installed=False,
        actual_account_performance=False,
        prospective_cycle_changed=False,
        limitations=[
            "Previously examined history and a current retrospective freeze do not create unseen out-of-sample evidence.",
            "A currently selected single ETF is not a historical market-wide or survivorship-free universe.",
            "Vendor-adjusted opening units have unverified historical publication/action semantics and are not executable quotes.",
            "Zero-yield USD cash omits account SGD/FX, real financing, taxes, spreads and impact.",
            "Annual NAV1 resets with entry/terminal fees are separate episodes, not a continuous account.",
            "Stock-change turnover is not the organizer daily turnover metric; target exposure does not establish eligibility.",
            "The declared model is unavailable; SMA/fixed exposure differences do not establish causal alpha or authorize adoption.",
        ],
    )
    table = "\n".join(
        f"|{c['episode']}|{c['arm']}|{c['fee_bps']}|{c['status']}|"
        + (
            f"{c['metrics']['total_return']:.6f}|{c['metrics']['maximum_drawdown']:.6f}|{c['metrics']['sum_trade_turnover']:.6f}|"
            if c["metrics"] is not None
            else "null|null|null|"
        )
        for c in cases
    )
    english = "# Common-ledger baseline study\n\nAll prices and annual episodes were already exposed. This is a retrospective USD adjusted-opening proxy with zero cash yield, common entry/rebalance/terminal fees and independent NAV1 resets. Drawdown includes initial wealth. No actual account, FX, financing, tax, spread or impact ledger is reconstructed. Partial years stay outside the full-year screen. All model-unavailable cases remain null. The screen compares SMA with the monthly fixed arm without exposure matching and authorizes no adoption. No prospective cycle or order is changed. See study.json for all paths, signals and trades.\n\n|Episode|Arm|Fee bp|Status|Return|Opening max drawdown|Turnover sum|\n|---|---|---:|---|---:|---:|---:|\n"
    chinese = "# 同账本基线比较\n\n全部价格与年度区间已经查看。本轮使用 USD 调整开盘代理、零收益现金和统一的入场、调仓、期末费用，各年从净值一重置，回撤包含初始资金。没有重建真实账户、汇率、融资、税、价差或冲击账本。部分年不进入完整年度筛选分母。模型不可用案例全部保留为空。均线与月度固定仓位比较没有匹配敞口，筛选结果不批准实际采用。前瞻周期和订单均未改变。完整净值、信号和交易见 study.json。\n\n|区间|方案|单边费用 bp|状态|收益|开盘最大回撤|换手合计|\n|---|---|---:|---|---:|---:|---:|\n"
    return _save(
        output,
        "study.json",
        value,
        [protocol_root, manifest_file.parent]
        + [Path(v["path"]).parent for v in manifest["sources"].values()],
        english + table,
        chinese + table,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.manifest, args.protocol, args.output)


if __name__ == "__main__":
    main()
