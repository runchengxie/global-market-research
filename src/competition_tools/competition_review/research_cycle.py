"""Freeze concrete research hypotheses and a future calendar, never account targets."""

import argparse
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, DecimalException
from importlib.metadata import version
from pathlib import Path

from competition_tools.crypto_evidence import digest
from .evidence import aware, START, END
from .shadow import _save
from .strategy_case import _snapshot


def _schedule(first_session, cutoff, now):
    import exchange_calendars as xc

    first = date.fromisoformat(first_session)
    if first.isoformat() != first_session:
        raise ValueError("CANONICAL_SESSION_DATE_REQUIRED")
    schedule = xc.get_calendar(
        "XNYS", start=first, end=first + timedelta(days=90)
    ).schedule
    rows = [
        dict(
            session_date=t.date().isoformat(),
            open=aware(r["open"].isoformat()).isoformat(),
            close=aware(r["close"].isoformat()).isoformat(),
        )
        for t, r in schedule.iterrows()
        if t.date() >= first
    ]
    if len(rows) < 22 or rows[0]["session_date"] != first_session:
        raise ValueError("EXACT_FIRST_RESEARCH_SESSION_REQUIRED")
    selected = rows[:22]
    initial = aware(selected[0]["close"]) + timedelta(minutes=30)
    entry, exit_at = aware(selected[1]["open"]), aware(selected[21]["open"])
    if not (START <= initial and now < initial < cutoff <= exit_at < END):
        raise ValueError("PROSPECTIVE_CYCLE_AND_MATERIAL_CUTOFF_REQUIRED")
    return dict(
        calendar="XNYS",
        calendar_status="research_scenario_not_official_contest_or_qualified_broker_calendar",
        package_version=version("exchange-calendars"),
        calendar_sha256=hashlib.sha256(
            json.dumps(selected, sort_keys=True).encode()
        ).hexdigest(),
        initial_signal_deadline=initial.isoformat(),
        entry=entry.isoformat(),
        exit=exit_at.isoformat(),
        daily_checks=[
            dict(
                session_date=r["session_date"],
                review_deadline=(aware(r["close"]) + timedelta(minutes=30)).isoformat(),
            )
            for r in selected[1:21]
        ],
        daily_checks_are_rebalances=False,
    )


def propose(
    snapshot_root, output, *, core_conid, first_session, material_deadline, now=None
):
    try:
        return _propose(
            snapshot_root,
            output,
            core_conid,
            first_session,
            material_deadline,
            aware((now or datetime.now(timezone.utc)).isoformat()),
        )
    except (
        KeyError,
        TypeError,
        AttributeError,
        DecimalException,
        OverflowError,
    ) as exc:
        raise ValueError("INVALID_RESEARCH_CYCLE") from exc


def _propose(snapshot_root, output, core_conid, first_session, material_deadline, now):
    root = Path(snapshot_root)
    snapshot, weights, _ = _snapshot(root, now)
    if sum((Decimal(v) for v in weights.values()), Decimal(0)) > 1:
        raise ValueError("ONLY_UNLEVERED_REFERENCE_SUPPORTED")
    if (
        not isinstance(core_conid, str)
        or not core_conid.isascii()
        or not core_conid.isdigit()
        or int(core_conid) <= 0
    ):
        raise ValueError("EXPLICIT_CORE_CONID_REQUIRED")
    selected = [
        p
        for p in snapshot["stock"]["positions"]
        if p["conid"] == core_conid
        and p["currency"] == "USD"
        and Decimal(p["quantity"]) > 0
    ]
    if len(selected) != 1:
        raise ValueError("CORE_MUST_BE_EXPLICIT_POSITIVE_HELD_USD_STOCK")
    cutoff = aware(material_deadline)
    schedule = _schedule(first_session, cutoff, now)
    fixed = {core_conid: "0.5"}
    candidates = [
        dict(
            id="observed_reference",
            initial_reference_stock_weights=weights,
            rule="Assume reported stock weights at common hypothetical entry; hold units for the common interval. Model the residual in base currency at zero return.",
            actual_account_buy_and_hold=False,
        ),
        dict(
            id="fixed_half",
            initial_reference_stock_weights=fixed,
            rule="One initial hypothetical change to 50% core and 50% base-currency residual; hold units throughout the interval.",
            actual_policy_approved=False,
        ),
        dict(
            id="initial_trend_half",
            initial_reference_stock_weights=None,
            signal_status="blocked_history_unverified",
            rule=dict(
                observations=200,
                signal="Initial completed-day split-adjusted USD close strictly above its 200-observation arithmetic mean including that day: 50% core; equality/below: 0%. Missing or unverifiable data: blocked, never off/cash.",
                risk_on_stock_weights=fixed,
                risk_off_stock_weights={},
                cadence="Initial decision only; no signal updates or recurring rebalancing during the 20-session observation interval.",
            ),
        ),
    ]
    result = dict(
        schema="competition.concrete_research_cycle.v1",
        status="frozen_research_proposal_awaiting_inputs",
        created_at=now.isoformat(),
        account_ref=snapshot["account_ref"],
        base_currency=snapshot["base_currency"],
        observed_report_date=snapshot["report_date"],
        snapshot_sha256=digest(root / "snapshot.json"),
        report_sha256=digest(root / "report.xml"),
        core_identity={k: selected[0][k] for k in ["conid", "symbol", "currency"]},
        core_market_identity_independently_verified=False,
        candidates=candidates,
        primary_simple_candidate="fixed_half",
        primary_benchmark="observed_reference",
        risk_matched_reference="fixed_half",
        allocation_parameters_are="unoptimized_research_hypotheses_not_account_risk_budget",
        fees=dict(
            one_way_bps=["0", "10", "25"],
            initial_stock_cost_formula="sum(abs(candidate_stock_weight-reference_stock_weight))*bps/10000",
            ongoing_rebalance_costs=False,
            terminal_liquidation_modeled=False,
            actual_costs_estimated=False,
        ),
        modeled_non_stock_return="0",
        schedule=schedule,
        material_review=dict(
            status="proposed_cutoff_team_acknowledgement_pending",
            cutoff=cutoff.isoformat(),
            required_deliverables=[
                "Declaration identifier and intended return-prediction objective/market/universe.",
                "Owner-reviewed PIT inputs, identity maps and factor-availability evidence.",
                "Training code revision, immutable fitted model/checkpoint hash and fit cutoff.",
                "Dated scores, frozen policy/target files and parent hashes.",
                "Contemporaneous account/decision/order references binding the declared model to actual holdings.",
            ],
            cutoff_action="If binding is still absent, retain unverified status and review prospective actual-policy/organizer path. Do not infer no local Ranker exists or retroactively explain earlier trades.",
            external_messages_sent=False,
        ),
        data_readiness=dict(
            status="blocked",
            needed=[
                "200 completed split-adjusted USD core closes with exact session labels and causal availability; no fitted or inferred SMA signal yet.",
                "Base-currency total-return observations for every reference/core conid at common interval endpoints, including dividend, FX and security-identity semantics.",
                "A reviewed cash/FX ledger before interpreting the normalized zero-return residual as actual account buy-and-hold.",
                "Contemporaneous decision records before the initial hypothetical entry and all daily checkpoints.",
            ],
        ),
        process_acceptance=dict(
            required_daily_checks=20,
            causal_or_reconstruction_errors_allowed=0,
            missing_observations="retain_as_missing_no_dropping_or_date_shifting",
            evaluation="one paired hypothetical interval with all fee scenarios; daily diagnostics require separately reconciled valuation inputs",
            superiority_after_one_cycle=False,
            adoption_after_one_cycle=False,
        ),
        actual_policy_confirmed=False,
        accepted_research=False,
        execution_authorized=False,
        scheduler_installed=False,
        actual_future_results=None,
        limitations=[
            "These are concrete proposed research rules, not a declared fundamental Ranker, personalized allocation or executable target.",
            "The observed-stock reference normalizes residual cash/accruals; actual multi-currency cash performance differs.",
            "Current observed weights are a dated reference, not verified future-entry holdings.",
            "The initial trend test is a one-decision experiment, not a dynamic trend backtest.",
            "Local clock/seal and calculated calendar do not independently authenticate pre-registration or trading eligibility.",
        ],
    )
    return _save(
        output,
        "proposal.json",
        result,
        [root],
        f"# Concrete research proposal\n\nResearch only: observed-stock reference; 50% explicit core/50% modeled residual; initial SMA200 choosing 0%/50% core and then holding for the same interval. All use the same 0/10/25bp cost scenarios. The 50% level is an unoptimized hypothesis, not an approved risk budget. The reference residual is modeled at zero, not literal multi-currency account cash.\n\nInitial signal: {schedule['initial_signal_deadline']}; hypothetical entry: {schedule['entry']}; exit: {schedule['exit']}. Twenty daily checks are observations, not rebalances. Missing verified history leaves the trend arm blocked. No actual future results, order or schedule exists.\n\nProposed material cutoff: {cutoff.isoformat()}; team acknowledgement pending. Local Ranker code does not establish declaration/checkpoint/score/account binding. See proposal.json for exact rules, required deliverables and data gaps. Full operating proposal: docs/operations/research-candidates.md.",
        f"# 具体研究候选\n\n仅用于研究：报表股票权重参考；50% 明确指定的核心标的加50% 模拟剩余部分；首次用200日均线选择0%/50% 核心标的，此后在同一区间持有。三组都报告0/10/25基点费用情景。50% 是未经优化的假设，不是已批准的风险预算。参考组合剩余部分按零收益模拟，不等于实际多币种现金。\n\n初始信号截止：{schedule['initial_signal_deadline']}；假设入场：{schedule['entry']}；退出：{schedule['exit']}。20次每日检查不是20次调仓。历史数据未核验，均线分支继续阻断。没有未来实际成绩、订单或定时任务。\n\n拟议材料截止：{cutoff.isoformat()}，尚待团队确认。本地存在 Ranker 代码，不等于已绑定申报、模型、评分和账户。proposal.json 保存完整规则、交付清单和数据缺口；操作提案见 docs/operations/research-candidates.zh-CN.md。",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--core-conid", required=True)
    p.add_argument("--first-session", required=True)
    p.add_argument("--material-deadline", required=True)
    a = p.parse_args()
    propose(
        a.snapshot,
        a.output,
        core_conid=a.core_conid,
        first_session=a.first_session,
        material_deadline=a.material_deadline,
    )
    print(
        "Research proposal saved; future inputs/results pending; no execution authorization."
    )


if __name__ == "__main__":
    main()
