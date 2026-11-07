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


def audit(declaration_root, snapshot_root, output, as_of):
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
    report = dict(
        schema="competition.private_audit.v1",
        as_of=as_of.isoformat(),
        declaration_receipt=receipt,
        declaration_independently_verified=False,
        observation_inventory=observations,
        calendar_scenarios=scenarios,
        official_eligibility="unverified",
        execution_authorized=False,
    )
    out = new_output(output, inputs=[declaration_root, snapshot_root])
    for name, value in [
        ("audit.json", report),
        ("policy-draft.json", policy),
        ("daily-review.json", review_decision(policy, {}, as_of)),
    ]:
        (out / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    (out / "report.zh-CN.md").write_text(
        """# 比赛策略私有审计

已有用户提供的正式申报资料，校验记录见 audit.json；本工具未独立登录平台核验。

当前结论：资格未知，调仓判断阻塞。没有生成交易指令。

- 声明采用 PIT 基本面横截面 Ranker。现有价格动量基线不能替代该声明的实现证据。
- 本地历史快照不是完整日账本，缺失日期不能按空仓或零换手计算。
- 平台显示的最新采集与本地快照是不同证据来源；本地陈旧不证明平台中断。
- XNYS、XTKS 仅为交易日情景，不是主办方确认的全球账户统计口径。
- 规则允许持仓路径或换手路径满足条件，并没有普遍要求为了交易次数而调仓。

下一步：获取主办方每日持仓率、换手率、空仓日定义和完整期间导出，核对账户绑定；补齐基准、PIT 因子、模型、评分、Top-K/进退缓冲、风险限额和当前市值权重。

policy-draft.json 的空值是待补证据，不能当默认参数。daily-review.json 记录阻塞原因；持仓不变不能据此认定为经过策略复核。平台比赛期间锁定编辑，涉及申报变更应遵循主办方流程。

公开规则：https://fundconnecthk.com/quant-league/legal/competition-rules/
""",
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
    args = parser.parse_args()
    as_of = aware(args.as_of) if args.as_of else datetime.now(timezone.utc)
    audit(args.declaration_root, args.snapshot_root, args.output, as_of)
    print("Private audit saved; eligibility unverified; no execution authorization.")


if __name__ == "__main__":
    main()
