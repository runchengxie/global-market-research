"""Offline same-label broker/platform evidence table, never official reconciliation."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from competition_tools.crypto_evidence import digest, read_json
from competition_tools.datasets.daily_storage import safe_path
from .evidence import aware
from .flex_client import parse_xml
from .flex_ledger import summarize_ledger
from .flex_reports import discover_report, report_date
from .shadow import _save
from .statements import load_statement_bundle
from .strategy_case import _declaration, _snapshot


def _join(broker_rows, execution_counts, platform_rows):
    broker = {r["report_date"]: r for r in broker_rows}
    platform = {r["session_date"]: r for r in platform_rows or []}
    if len(broker) != len(broker_rows) or len(platform) != len(platform_rows or []):
        raise ValueError("DUPLICATE_DAILY_LABEL")
    rows = []
    for day in sorted(broker.keys() | platform.keys() | execution_counts.keys()):
        b, p = broker.get(day), platform.get(day)
        proxy = b["stock_exposure_proxy"] if b else None
        supplied = p["position_rate"] if p else None
        if platform_rows is None:
            status = "missing_platform_evidence"
        elif p is None:
            status = "broker_date_outside_supplied_elapsed_calendar"
        elif b is None:
            status = "platform_calendar_day_without_broker_nav"
        else:
            status = "same_label_requires_semantic_review"
        rows.append(
            dict(
                date_label=day,
                broker_nav=b["nav"] if b else None,
                broker_stock_gross_value=b["stock_gross_value"] if b else None,
                broker_stock_exposure_proxy=proxy,
                reported_execution_records=execution_counts.get(day, 0 if b else None),
                platform_position_rate=supplied,
                platform_turnover_rate=p["turnover_rate"] if p else None,
                platform_flat_day=p["flat_day"] if p else None,
                platform_day_evidence=p["evidence"] if p else "missing",
                numeric_proxy_minus_platform_position=str(
                    Decimal(proxy) - Decimal(supplied)
                )
                if proxy is not None and supplied is not None
                else None,
                metric_equivalence="unconfirmed",
                status=status,
            )
        )
    return rows


def run(declaration_root, snapshot_root, output, *, statement_bundle=None, now=None):
    stamp = aware((now or datetime.now(timezone.utc)).isoformat())
    declaration_root = safe_path(Path(declaration_root))
    snapshot_root = safe_path(Path(snapshot_root))
    declaration_hash = _declaration(declaration_root)
    snapshot, _, _ = _snapshot(snapshot_root, stamp)
    raw = (snapshot_root / "report.xml").read_bytes()
    account = discover_report(raw)["accounts"][0]
    ledger = summarize_ledger(raw, expected_account=account)
    if (snapshot_root / "ledger.json").exists() and read_json(
        snapshot_root / "ledger.json"
    ) != ledger:
        raise ValueError("LEDGER_REPRODUCTION_MISMATCH")
    counts, seen = Counter(), set()
    for row in parse_xml(raw).findall("./FlexStatements/FlexStatement/Trades/Trade"):
        if row.get("levelOfDetail") == "EXECUTION" and row.get("tradeID") not in seen:
            seen.add(row.get("tradeID"))
            counts[report_date(row.get("tradeDate"))] += 1
    if any(
        day > stamp.date().isoformat()
        for day in set(counts) | {r["report_date"] for r in ledger["reported_nav"]}
    ):
        raise ValueError("FUTURE_BROKER_DATE")
    statement = None
    inputs = [declaration_root, snapshot_root]
    if statement_bundle is not None:
        statement = load_statement_bundle(
            statement_bundle, stamp, declaration_sha256=declaration_hash
        )
        if (
            statement["account_ref"] != snapshot["account_ref"]
            or statement["base_currency"] != snapshot["base_currency"]
        ):
            raise ValueError("PLATFORM_ACCOUNT_OR_CURRENCY_MISMATCH")
        inputs += [Path(statement["bundle_path"])] + [
            Path(v["path"]) for v in statement["sources"].values()
        ]
    rows = _join(
        ledger["reported_nav"],
        counts,
        statement["daily_coverage"] if statement else None,
    )
    result = dict(
        schema="competition.daily_evidence_reconciliation.v1",
        recorded_at=stamp.isoformat(),
        account_ref=snapshot["account_ref"],
        base_currency=snapshot["base_currency"],
        declaration_sha256=declaration_hash,
        snapshot_sha256=digest(snapshot_root / "snapshot.json"),
        report_sha256=digest(snapshot_root / "report.xml"),
        platform_status="supplied_attributed_bundle" if statement else "missing",
        platform_statement=statement,
        broker_ledger=ledger,
        days=rows,
        row_status_counts=dict(Counter(r["status"] for r in rows)),
        session_label_mapping="identical_labels_only_not_independently_verified",
        metric_equivalence="unconfirmed",
        official_eligibility="unverified",
        execution_authorized=False,
        missing_or_review_items=[
            "Account-bound platform raw daily export and reviewed fractional normalization.",
            "Full official calendar, timezone and session-label mapping to broker report dates.",
            "Position/turnover/flat-day definitions, intraday, FX and derivatives treatment.",
            "Confirm semantic comparability before interpreting numeric gaps or zero differences.",
        ],
    )

    def display(value):
        return "—" if value is None else str(value)

    table = "\n".join(
        "|"
        + "|".join(
            display(r[k])
            for k in [
                "date_label",
                "broker_stock_exposure_proxy",
                "reported_execution_records",
                "platform_position_rate",
                "platform_turnover_rate",
                "platform_flat_day",
                "numeric_proxy_minus_platform_position",
                "status",
            ]
        )
        + "|"
        for r in rows
    )
    return _save(
        output,
        "reconciliation.json",
        result,
        inputs,
        "# Daily platform and broker evidence\n\nSame-label descriptive table only. Broker stock gross/NAV is not the organizer position rate, and execution counts are not turnover. Zero or nonzero numeric gaps do not establish agreement/error. Missing rows remain null; zero reported executions does not prove no actual trading or a flat day. Definitions, timezones and calendar alignment remain unconfirmed; even supplied organizer_confirmed labels are attributed, not independent authentication. No eligibility certificate or trading instruction.\n\n|Date label|Stock proxy (fraction)|Reported executions|Supplied position|Supplied turnover|Supplied flat day|Numeric proxy−supplied|Status|\n|---|---:|---:|---:|---:|---|---:|---|\n"
        + table
        + "\n\nFull source hashes, statement references, ledger and open review items: reconciliation.json.",
        "# 平台指标—券商账本逐日证据表\n\n这里只按相同日期标签并列展示。券商股票总值/NAV不是主办方持仓率，执行笔数不是换手率。数值差为零不能证明一致，差不为零也不能直接判错。缺失保留为空；零笔已报告执行不证明当日没有交易或属于空仓日。公式、时区和日历映射尚未独立确认；即使输入标记organizer_confirmed，也只是有来源的归属声明。本表不认证比赛资格，不提供交易指令。\n\n|日期标签|股票敞口代理（比例）|已报告执行笔数|所提供持仓率|所提供换手率|所提供空仓日|代理值减所提供值|状态|\n|---|---:|---:|---:|---:|---|---:|---|\n"
        + table
        + "\n\n完整来源哈希、提供的日历/公式、重算账本与待核对项见reconciliation.json。",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--declaration-root", required=True)
    parser.add_argument("--snapshot-root", required=True)
    parser.add_argument("--statement-bundle")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(
        args.declaration_root,
        args.snapshot_root,
        args.output,
        statement_bundle=args.statement_bundle,
    )
    print(
        "Platform evidence: "
        + result["platform_status"]
        + "; official eligibility unverified; no execution."
    )


if __name__ == "__main__":
    main()
