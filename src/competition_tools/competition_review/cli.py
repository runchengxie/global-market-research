"""Offline private review. No network, broker collection or executable targets."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from competition_tools.crypto_evidence import digest, read_json, new_output, seal
from competition_tools.datasets.daily_storage import safe_path
from .evidence import aware, load_observations, calendar_scenario
from .participation import daily_rows, summarize_days, future_bounds
from .decision import review_decision
from .statements import load_statement_bundle


def audit(
    declaration_root,
    snapshot_root,
    output,
    as_of,
    *,
    statement_bundle=None,
    policy_file=None,
    decision_inputs=None,
):
    if (policy_file is None) != (decision_inputs is None):
        raise ValueError("POLICY_AND_DECISION_INPUTS_REQUIRED_TOGETHER")
    declaration_root = safe_path(Path(declaration_root))
    snapshot_root = safe_path(Path(snapshot_root))
    receipt = read_json(declaration_root / "receipt.json")
    expected = {"declaration.json", "declaration.md", "declaration.zh-CN.md"}
    if {r["path"] for r in receipt["files"]} != expected or len(receipt["files"]) != 3:
        raise ValueError("INVALID_DECLARATION_RECEIPT")
    for record in receipt["files"]:
        if digest(declaration_root / record["path"]) != record["sha256"]:
            raise ValueError("DECLARATION_RECEIPT_MISMATCH")
    observations = load_observations(snapshot_root, as_of)
    scenarios = []
    for name in ["XNYS", "XTKS"]:
        scenario = calendar_scenario(name, as_of)
        rows = daily_rows(scenario["elapsed_sessions"], [])
        scenario["daily_coverage"] = rows
        scenario["summary"] = summarize_days(rows) if rows else None
        scenario["position_planning"] = future_bounds(
            0, 0, len(rows), len(scenario["remaining_sessions"])
        )
        scenarios.append(scenario)
    policy = dict(
        schema="competition.policy_draft.v1",
        status="draft",
        scope="prospective_only",
        declaration_sha256=digest(declaration_root / "declaration.json"),
        approach="declared_pit_fundamental_cross_sectional_ranker",
        account_ref=None,
        top_k=None,
        entry_buffer=None,
        exit_buffer=None,
        name_cap=None,
        gross_cap=None,
        turnover_cap=None,
        drift_band=None,
        max_age_hours=None,
        missing_evidence=[
            "benchmark",
            "pit_universe_and_factors",
            "ranker_checkpoint",
            "dated_scores",
            "reviewed_target_weights",
            "marked_position_weights",
            "official_daily_statements_and_calendar",
        ],
    )
    declaration_hash = digest(declaration_root / "declaration.json")
    statement = (
        load_statement_bundle(
            statement_bundle, as_of, declaration_sha256=declaration_hash
        )
        if statement_bundle
        else None
    )
    inputs = {}
    evidence_inputs = [declaration_root, snapshot_root]
    provided_records = {}
    if statement:
        evidence_inputs.extend(
            [
                Path(statement["bundle_path"]),
                *[Path(v["path"]) for v in statement["sources"].values()],
            ]
        )
    if policy_file:
        for key, value in [("policy", policy_file), ("inputs", decision_inputs)]:
            value = safe_path(Path(value))
            provided_records[key] = dict(path=str(value), sha256=digest(value))
            evidence_inputs.append(value)
        policy = read_json(policy_file)
        inputs = read_json(decision_inputs)
        if (
            policy.get("declaration_sha256") != declaration_hash
            or inputs.get("declaration_sha256") != declaration_hash
        ):
            raise ValueError("DAILY_REVIEW_DECLARATION_MISMATCH")
        if statement and any(
            v.get("account_ref") != statement["account_ref"] for v in [policy, inputs]
        ):
            raise ValueError("DAILY_REVIEW_ACCOUNT_MISMATCH")
    decision = review_decision(policy, inputs, as_of)
    report = dict(
        schema="competition.private_audit.v1",
        as_of=as_of.isoformat(),
        declaration_receipt=receipt,
        declaration_independently_verified=False,
        observation_inventory=observations,
        reviewed_statement=statement,
        supplied_daily_evidence=provided_records,
        calendar_scenarios=scenarios,
        official_eligibility="unverified",
        execution_authorized=False,
    )
    out = new_output(output, inputs=evidence_inputs)
    for name, value in [
        ("audit.json", report),
        ("policy-review.json" if policy_file else "policy-draft.json", policy),
        ("daily-review.json", decision),
    ]:
        (out / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    summary = statement["summary"] if statement else None
    coverage = (
        "No reviewed daily statement supplied."
        if summary is None
        else json.dumps(summary, ensure_ascii=False)
    )
    (out / "report.md").write_text(
        "# Private competition review\n\n[简体中文](report.zh-CN.md)\n\n"
        + f"Official eligibility: unverified. Daily review: {decision['status']}. No execution authorization.\n\n"
        + "Reviewed elapsed daily arithmetic (attributed inputs, not source authentication):\n\n"
        + coverage
        + "\n\n"
        + "Local snapshots are observation proxies, not complete daily statements. Missing days remain unknown. "
        + "Platform and local collection freshness are separate. XNYS/XTKS remain calendar scenarios. "
        + "A supplied calendar is a reviewed completeness assertion, not an independently verified calendar.\n\n"
        + "Recover official daily exports and ratio definitions/account binding; then establish PIT universe/factors, "
        + "benchmark, Ranker checkpoint, dated scores, buffers, risk limits and marked current weights. "
        + "Price-only research does not establish implementation of a declared fundamental Ranker. "
        + "Do not rebalance solely to manufacture trade counts. Respect platform edit locks.\n",
        encoding="utf-8",
    )
    (out / "report.zh-CN.md").write_text(
        "# 比赛策略私有复核\n\n[English](report.md)\n\n"
        + f"官方资格：未核实。每日复核：{decision['status']}。没有交易授权。\n\n"
        + "已过去日期的账本计算（来自所提供的记录，不代表独立来源认证）：\n\n"
        + coverage
        + "\n\n"
        + "本地快照是观察值，不是完整日账本；缺失日期仍为未知。平台采集与本地采集分别检查。"
        + "XNYS/XTKS 仅为日历情景。提供的日历完整性属于复核者声明，并非独立核验。\n\n"
        + "下一步：获取官方每日导出、指标定义和账户绑定；补齐 PIT 投资池/因子、基准、Ranker、"
        + "带日期评分、进退缓冲、风险限额及当前市值权重。价格研究不能证明申报基本面 Ranker 已执行。"
        + "不要为了凑交易次数而调仓，申报变更遵循平台锁定和主办方流程。\n",
        encoding="utf-8",
    )
    seal(out)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--declaration-root", required=True)
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--as-of")
    parser.add_argument("--statement-bundle")
    parser.add_argument("--policy")
    parser.add_argument("--decision-inputs")
    args = parser.parse_args()
    as_of = aware(args.as_of) if args.as_of else datetime.now(timezone.utc)
    audit(
        args.declaration_root,
        args.snapshot_root,
        args.output,
        as_of,
        statement_bundle=args.statement_bundle,
        policy_file=args.policy,
        decision_inputs=args.decision_inputs,
    )
    print("Private audit saved; eligibility unverified; no execution authorization.")


if __name__ == "__main__":
    main()
