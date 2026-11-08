"""Manual prospective diary and paired hypothetical observations, never orders."""

from datetime import datetime, timezone
from decimal import Decimal, DecimalException
from pathlib import Path
import json

from competition_tools.crypto_evidence import (
    digest,
    read_json,
    new_output,
    seal,
    verify_seal,
)
from competition_tools.datasets.daily_storage import safe_path
from .evidence import aware
from .participation import decimal
from .strategy_case import build_case


def _now(now):
    return aware((now or datetime.now(timezone.utc)).isoformat())


def _save(output, name, value, inputs, english, chinese):
    out = new_output(output, inputs=inputs)
    out.chmod(0o700)
    (out / name).write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (out / "report.md").write_text(
        "[简体中文](report.zh-CN.md)\n\n" + english + "\n", encoding="utf-8"
    )
    (out / "report.zh-CN.md").write_text(
        "[English](report.md)\n\n" + chinese + "\n", encoding="utf-8"
    )
    for p in out.iterdir():
        p.chmod(0o600)
    seal(out)
    (out / "seal.json").chmod(0o600)
    return value


def _inputs(case_file, review):
    paths = [safe_path(Path(case_file))]
    for key, row in review["file_records"].items():
        p = Path(row["path"])
        paths.append(p.parent if key in {"declaration", "snapshot"} else p)
    return paths


def prepare(case_file, output, *, now=None):
    stamp = _now(now)
    review = build_case(case_file, stamp)
    charter = dict(
        schema="competition.prospective_charter.v1",
        status="draft",
        created_at=stamp.isoformat(),
        account_ref=review["account_ref"],
        declaration_sha256=review["file_records"]["declaration"]["sha256"],
        observed_report_date=review["report_date"],
        observed_weights=review["current_weights"],
        approach=None,
        benchmark=None,
        target_weights=None,
        risk_limits=None,
        review_calendar=None,
        review_owner=None,
        confirmed_at=None,
        confirmed_by=None,
        research_lanes={
            "competition": "Recover declaration-aligned evidence or document actual prospective policy and resolve platform restrictions.",
            "crypto": "Separate data/venue/benchmark/cost/out-of-sample protocol; no competition handoff.",
            "moe": "Separate architecture/baseline/ablation/multiple-seed and forward-period evidence; no competition handoff.",
        },
        promotion_requirements=[
            "Freeze data availability, decision/entry timing, benchmark, fees and risk rules before later observations.",
            "Compare paired out-of-sample periods and uncertainty; one favorable interval is insufficient.",
            "Any competition execution requires its own reviewed contract and separate authorization.",
        ],
        unresolved_choices=[
            "Recover declared fundamental Ranker versus document actual policy prospectively; never rewrite past rationale.",
            "Choose benchmark, allocation rationale, limits, cadence, pause conditions and accountable reviewer.",
        ],
        case_sha256=digest(case_file),
        execution_authorized=False,
    )
    return _save(
        output,
        "charter-draft.json",
        charter,
        _inputs(case_file, review),
        "# Prospective strategy draft\n\nStatus: draft, not a frozen or confirmed policy. Observed holdings are a reference, not target weights. Benchmark, allocation and risk decisions remain null. See charter-draft.json for missing decisions and distinct competition/crypto/MoE research lanes. Resolve the declared Ranker evidence or document the actual policy prospectively through the organizer's process. Do not use a new policy as a historical explanation. No broker/scheduler/platform changes or orders.",
        "# 面向未来的策略草案\n\n状态：草案，尚未冻结或确认。观察持仓仅作参考，不是目标权重。基准、配置和风险参数保留为空。charter-draft.json 列出待决定事项及比赛、加密货币、MoE 的独立研究路径。先恢复申报 Ranker 的证据，或如实记录实际策略并遵循主办方变更流程；新策略不能成为过去交易的解释。未改动券商、定时任务或平台，没有订单。",
    )


def _protocol(case_file, review, stamp):
    window = read_json(case_file).get("shadow_window")
    if review["comparison"] is None or window is None:
        return None
    start, end = aware(window["start"]), aware(window["end"])
    if not stamp <= start < end:
        raise ValueError("PROSPECTIVE_SHADOW_WINDOW_REQUIRED")
    ref = review["file_records"]["policy"]
    path = safe_path(Path(ref["path"]))
    if digest(path) != ref["sha256"]:
        raise ValueError("POLICY_CHANGED_DURING_RECORDING")
    return dict(
        start=start.isoformat(),
        end=end.isoformat(),
        benchmark=read_json(path)["benchmark"],
        one_way_cost_bps=review["comparison"]["one_way_cost_bps"],
    )


def record(case_file, output, *, now=None):
    stamp = _now(now)
    review = build_case(case_file, stamp)
    status = review["daily_review"]["status"]
    result = dict(
        schema="competition.shadow_decision.v1",
        recorded_at=stamp.isoformat(),
        intent="blocked_evidence_review"
        if status == "blocked"
        else status + "_not_order",
        review=review,
        evaluation_protocol=_protocol(case_file, review, stamp),
        timestamp_authentication="local_clock_only",
        execution_authorized=False,
    )
    return _save(
        output,
        "decision.json",
        result,
        _inputs(case_file, review),
        f"# Prospective shadow entry\n\nRecorded at {stamp.isoformat()}; historical holdings report date {review['report_date']}. Review status: {status}. Blocked evidence is not a maintain instruction. Entries use local current time, not a trusted timestamp. Manual recording only; no scheduled job or order. Later outcome files must bind this decision's hash and a strictly later interval; never rewrite this entry after seeing results.",
        f"# 事前影子决策记录\n\n记录时间 {stamp.isoformat()}；历史持仓报表日 {review['report_date']}。复核状态：{status}。证据阻断不等于决定继续持有。时间来自本机当前时钟，不是权威时间戳。这里只做手动记录，没有启动定时任务或下单。后续观察必须绑定本次文件哈希及之后的时间区间，不能看到结果后修改这条记录。",
    )


def _return(value):
    if type(value) not in (str, int, float, Decimal):
        raise ValueError("INVALID_RETURN")
    n = Decimal(str(value))
    if not n.is_finite() or n < -1:
        raise ValueError("INVALID_RETURN")
    return n


def interval_arithmetic(
    current_weights,
    target_weights,
    asset_returns,
    non_stock_return,
    benchmark_return,
    cost_bps,
):
    """Plain one-interval arithmetic only; no source/decision or execution approval."""
    try:
        return _interval_arithmetic(
            current_weights,
            target_weights,
            asset_returns,
            non_stock_return,
            benchmark_return,
            cost_bps,
        )
    except (KeyError, TypeError, DecimalException, OverflowError) as exc:
        raise ValueError("INVALID_INTERVAL_ARITHMETIC") from exc


def _interval_arithmetic(
    current_weights,
    target_weights,
    asset_returns,
    non_stock_return,
    benchmark_return,
    cost_bps,
):
    current = {k: decimal(v) for k, v in current_weights.items()}
    target = {k: decimal(v) for k, v in target_weights.items()}
    if sum(current.values()) > 1 or sum(target.values()) > 1:
        raise ValueError("ONLY_UNLEVERED_SLEEVES_SUPPORTED")
    returns = {k: _return(v) for k, v in asset_returns.items()}
    if set(returns) != current.keys() | target.keys():
        raise ValueError("OUTCOME_RETURN_KEYS_MISMATCH")
    non_stock = _return(non_stock_return)
    benchmark = _return(benchmark_return)
    bps = decimal(cost_bps)
    if bps > 10000:
        raise ValueError("INVALID_COST_BPS")

    def weighted(weights):
        return (
            sum((v * returns[k] for k, v in weights.items()), Decimal(0))
            + (1 - sum(weights.values())) * non_stock
        )

    turnover = sum(
        (abs(target.get(k, 0) - current.get(k, 0)) for k in returns), Decimal(0)
    )
    cost = turnover * bps / 10000
    maintain = weighted(current)
    changed = weighted(target) - cost
    if changed < -1:
        raise ValueError("HYPOTHETICAL_EQUITY_BELOW_ZERO")
    return dict(
        maintain_return=str(maintain),
        target_return_after_initial_cost=str(changed),
        paired_difference=str(changed - maintain),
        benchmark_return=str(benchmark),
        maintain_excess_over_benchmark=str(maintain - benchmark),
        target_excess_over_benchmark=str(changed - benchmark),
        initial_two_way_stock_turnover=str(turnover),
        initial_cost_fraction=str(cost),
    )


def evaluate(entry_root, outcome_file, output, *, now=None):
    try:
        return _evaluate(entry_root, outcome_file, output, _now(now))
    except (
        KeyError,
        TypeError,
        AttributeError,
        DecimalException,
        OverflowError,
    ) as exc:
        raise ValueError("INVALID_SHADOW_OBSERVATION") from exc


def _evaluate(entry_root, outcome_file, output, now):
    root = safe_path(Path(entry_root))
    source = safe_path(Path(outcome_file))
    verify_seal(root)
    decision = read_json(root / "decision.json")
    o = read_json(source)
    if (
        decision["schema"] != "competition.shadow_decision.v1"
        or o["schema"] != "competition.shadow_outcome.v1"
    ):
        raise ValueError("INVALID_SHADOW_SCHEMA")
    review = decision["review"]
    if review["daily_review"]["status"] == "blocked" or review["comparison"] is None:
        raise ValueError("BLOCKED_DECISION_CANNOT_BE_EVALUATED")
    if (
        o["decision_sha256"] != digest(root / "decision.json")
        or o["account_ref"] != review["account_ref"]
        or o["base_currency"] != review["base_currency"]
    ):
        raise ValueError("OUTCOME_BINDING_MISMATCH")
    if (
        not aware(decision["recorded_at"])
        <= aware(o["start"])
        < aware(o["end"])
        <= aware(o["available_at"])
        <= now
    ):
        raise ValueError("NONCAUSAL_OUTCOME")
    protocol = decision.get("evaluation_protocol")
    if protocol is None:
        raise ValueError("SHADOW_PROTOCOL_NOT_REGISTERED")
    if (
        aware(o["start"]) != aware(protocol["start"])
        or aware(o["end"]) != aware(protocol["end"])
        or o["benchmark"] != protocol["benchmark"]
        or decimal(o["one_way_cost_bps"]) != decimal(protocol["one_way_cost_bps"])
    ):
        raise ValueError("FROZEN_SHADOW_PROTOCOL_MISMATCH")
    target_ref = review["file_records"]["target"]
    target_path = safe_path(Path(target_ref["path"]))
    if digest(target_path) != target_ref["sha256"]:
        raise ValueError("RECORDED_TARGET_CHANGED")
    comparison = interval_arithmetic(
        review["current_weights"],
        read_json(target_path)["weights"],
        o["returns"],
        o["non_stock_return"],
        o["benchmark_return"],
        o["one_way_cost_bps"],
    )
    result = dict(
        schema="competition.shadow_comparison.v1",
        scope="hypothetical_one_interval_start_weights_not_broker_performance",
        decision_sha256=o["decision_sha256"],
        outcome_sha256=digest(source),
        evaluated_at=now.isoformat(),
        interval_start=o["start"],
        interval_end=o["end"],
        base_currency=review["base_currency"],
        **comparison,
        statistical_superiority_established=False,
        execution_authorized=False,
        limitations=[
            "One interval of attributed base-currency total returns; no execution, fills, cash flows or multi-period reinvestment simulated.",
            "Start-of-interval weights are hypothetical; residual sleeve includes cash/accruals, not available funds.",
            "Equal supplied non-stock sleeve return for both variants; initial linear costs only, no taxes/impact/financing or liquidation cost.",
            "Local seal and timestamps do not independently authenticate an actual ex-ante decision or market observations.",
        ],
    )
    return _save(
        output,
        "comparison.json",
        result,
        [root, source, target_path],
        "# Later paired observation\n\nHypothetical one-interval arithmetic only, not broker performance, a trading recommendation or proof of superiority. Initial recorded weights are assumed at interval start; no fills or cash flows simulated. See comparison.json for exact returns, initial stock-turnover cost, benchmark excess and limitations.",
        "# 后续配对观察\n\n仅为一个区间的假设计算，不是账户实际业绩、交易建议或优越性证明。假设区间起点持有记录中的权重，未模拟成交或资金流。comparison.json 保存收益、初始股票换手费用、相对基准结果及局限。",
    )
