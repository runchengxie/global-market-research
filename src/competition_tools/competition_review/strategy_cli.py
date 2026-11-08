"""Offline, file-backed private strategy review; never an execution handoff."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from competition_tools.crypto_evidence import new_output, seal
from .evidence import aware
from .strategy_case import build_case


def run(case_file, output, decision_time):
    result = build_case(case_file, decision_time)
    sources = [Path(r["path"]) for r in result["file_records"].values()]
    # Protect entire evidence bundles, including seals and unreferenced source files.
    sources.extend(
        Path(r["path"]).parent
        for k, r in result["file_records"].items()
        if k in {"declaration", "snapshot"}
    )
    out = new_output(output, inputs=sources)
    out.chmod(0o700)
    body = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    (out / "review.json").write_text(body, encoding="utf-8")
    status = result["daily_review"]["status"]
    missing = ", ".join(result["missing_roles"]) or "—"
    weights = json.dumps(result["current_weights"], ensure_ascii=False)
    comparison = json.dumps(result["comparison"], indent=2, ensure_ascii=False)
    (out / "report.md").write_text(
        f"# Private strategy evidence review\n\n[简体中文](report.zh-CN.md)\n\n"
        f"Review: **{status}**. Observed report date: **{result['report_date']}**, not real-time holdings. "
        "No execution authorization. Official eligibility and platform account binding remain unverified.\n\n"
        f"Missing file roles: {missing}. Current conid weights: `{weights}`.\n\n"
        "The Flex seal, raw-report hash and recomputed stock/cash snapshot were checked. "
        "Provided source files have verified byte hashes and attributed timestamps/parents; "
        "this does not prove PIT completeness, model semantics, predictive skill or independent source authenticity. "
        "A newly frozen policy cannot explain earlier trades retrospectively.\n\n"
        "Comparison is null when evidence blocks review. Otherwise it is static weight arithmetic and "
        "explicit hypothetical proportional stock shocks/linear cost, not a backtest, forecast or recommended allocation. "
        "The non-stock residual includes cash and accruals; it is not available cash.\n\n"
        f"```json\n{comparison}\n```\n\n"
        "Next: supply an attributed prospective policy with benchmark and limits; PIT/universe, model checkpoint, "
        "dated scores and reviewed target files. Freeze these before evaluating later observations. "
        "Then compare paired out-of-sample decisions with fees, FX and risk constraints. "
        "Do not trade simply to increase transaction counts. Detailed blockers and provenance are in review.json.\n",
        encoding="utf-8",
    )
    (out / "report.zh-CN.md").write_text(
        f"# 策略证据私有复核\n\n[English](report.md)\n\n"
        f"复核状态：**{status}**。持仓报表日：**{result['report_date']}**，不是实时持仓。"
        "没有交易授权；官方资格和平台账户绑定仍未核实。\n\n"
        f"缺少的文件角色：{missing}。按 conid 记录的观察权重：`{weights}`。\n\n"
        "已检查 Flex 封存、原始报表哈希，并从原始 XML 重新计算股票、现金对账。"
        "已提供文件的字节哈希、所声明的时间与父级关联经过核对；这不证明 PIT 完整、模型语义正确、"
        "预测有效或来源已独立认证。现在冻结的策略不能倒推为过去交易的依据。\n\n"
        "证据阻断时比较结果为 null。否则只计算权重变化及明确假设的股票同比例冲击和线性费用，"
        "不是回测、预测或配置建议。非股票剩余比例包含现金及应计项目，不等于可用现金。\n\n"
        f"```json\n{comparison}\n```\n\n"
        "下一步：补齐面向未来、注明确认人的策略及基准、风险限额，PIT/投资池、模型、带日期评分和复核后的目标文件。"
        "先冻结依据，再评价后续观察；随后做同日期的样本外决策比较，纳入费用、汇率与风险约束。"
        "不要为了增加成交次数而交易。具体阻断项与来源记录见 review.json。\n",
        encoding="utf-8",
    )
    for p in out.iterdir():
        p.chmod(0o600)
    seal(out)
    (out / "seal.json").chmod(0o600)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--as-of")
    args = parser.parse_args()
    result = run(
        args.case,
        args.output,
        aware(args.as_of) if args.as_of else datetime.now(timezone.utc),
    )
    print(
        json.dumps(
            dict(
                status=result["daily_review"]["status"],
                missing_roles=result["missing_roles"],
                execution_authorized=False,
            )
        )
    )


if __name__ == "__main__":
    main()
