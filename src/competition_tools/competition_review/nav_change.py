"""Reported MTM-mode NAV field arithmetic; not pure security-price/FX attribution."""

from datetime import datetime, timezone
from decimal import Decimal, DecimalException
from pathlib import Path

from competition_tools.crypto_evidence import digest
from .flex_client import parse_xml, FlexError
from .flex_reports import discover_report, report_date, _number
from .strategy_case import _snapshot
from .shadow import _save

COMPONENTS = set(
    "mtm mtmAtPaxos depositsWithdrawals carbonCredits donations internalCashTransfers paxosTransfers excessFundSweep assetTransfers debitCardActivity billPay grantActivity dividends withholdingTax withholding871m withholdingTaxCollected changeInDividendAccruals changeInLiteSurchargeAccruals changeInCGTWithholdingAccruals interest changeInInterestAccruals changeInIncentiveCouponAccruals brokerFees changeInBrokerFeeAccruals advisorFees clientFees otherFees otherIncome feesReceivables commissions commissionsAtPaxos referralFee commissionCreditsRedemption commissionReceivables transactionTax taxReceivables salesTax billableSalesTax softDollars netFxTrading fxTranslation linkingAdjustments other corporateActionProceeds".split()
)
INACTIVE = {
    "realized",
    "changeInUnrealized",
    "costAdjustments",
    "transferredPnlAdjustments",
    "forexCommissions",
}
META = {
    "accountId",
    "acctAlias",
    "model",
    "currency",
    "fromDate",
    "toDate",
    "startingValue",
    "endingValue",
    "twr",
}
TOLERANCE = Decimal("0.02")
REFERENCE = (
    "https://www.ibkrguides.com/reportingreference/reportguide/changeinnav_fq.htm"
)


def explain_nav(raw, *, expected_account, base_currency):
    try:
        return _explain_nav(raw, expected_account, base_currency)
    except (KeyError, TypeError, DecimalException, FlexError) as exc:
        raise ValueError("INVALID_NAV_CHANGE_REPORT") from exc


def _explain_nav(raw, expected_account, base_currency):
    if discover_report(raw)["accounts"] != [expected_account]:
        raise ValueError("NAV_ACCOUNT_MISMATCH")
    root = parse_xml(raw)
    rows = []
    for statement in root.findall("./FlexStatements/FlexStatement"):
        for row in statement.findall("./ChangeInNAV"):
            attrs = dict(row.attrib)
            if (
                row.get("accountId") != expected_account
                or row.get("currency") != base_currency
                or row.get("model")
            ):
                raise ValueError("NAV_ROW_IDENTITY_OR_MODEL_MISMATCH")
            start, end = (
                report_date(row.get("fromDate")),
                report_date(row.get("toDate")),
            )
            if (
                start > end
                or start != report_date(statement.get("fromDate"))
                or end != report_date(statement.get("toDate"))
            ):
                raise ValueError("NAV_PERIOD_MISMATCH")
            if attrs not in rows:
                rows.append(attrs)
    if len(rows) != 1:
        raise ValueError("ONE_UNAMBIGUOUS_NAV_PERIOD_REQUIRED")
    row = rows[0]
    if "mtm" not in row:
        raise ValueError("EXPLICIT_MTM_MODE_REQUIRED")
    beginning = Decimal(_number(row["startingValue"], positive=True))
    ending = Decimal(_number(row["endingValue"], positive=True))
    for key in INACTIVE:
        if row.get(key) and Decimal(_number(row[key])) != 0:
            raise ValueError("MIXED_OR_UNSUPPORTED_NAV_PROFIT_MODE")
    unknown = []
    for key in row.keys() - COMPONENTS - INACTIVE - META:
        if row[key] not in ("", "0"):
            raise ValueError("UNKNOWN_NONZERO_NAV_COMPONENT")
        unknown.append(key)
    values = {
        key: Decimal(_number(row[key])) for key in sorted(COMPONENTS & row.keys())
    }
    total = sum(values.values(), Decimal(0))
    change = ending - beginning
    residual = change - total
    if abs(residual) > TOLERANCE:
        raise ValueError("NAV_COMPONENTS_DO_NOT_RECONCILE")
    return dict(
        schema="competition.reported_nav_bridge.v1",
        status="reconciled_reported_components",
        period_start=report_date(row["fromDate"]),
        period_end=report_date(row["toDate"]),
        base_currency=base_currency,
        starting_nav=str(beginning),
        ending_nav=str(ending),
        nav_change=str(change),
        reported_components={k: str(v) for k, v in values.items()},
        reported_component_sum=str(total),
        residual=str(residual),
        tolerance_base_units=str(TOLERANCE),
        omitted_component_fields=sorted(COMPONENTS - row.keys()),
        unknown_zero_fields=sorted(unknown),
        reported_twr_raw=row.get("twr"),
        twr_recomputed=False,
        pure_security_price_fx_attribution_verified=False,
        field_semantics_independently_verified=False,
        official_eligibility="unverified",
        execution_authorized=False,
        reference=REFERENCE,
        limitations=[
            "Arithmetic on broker-reported fields, not a reconstruction of PnL from prices and executions.",
            "MTM may contain FX; separately reported netFxTrading/fxTranslation are not a complete isolated currency attribution. Do not relabel MTM as pure stock-price PnL.",
            "No MTM-performance, cash transaction or execution-commission rows added again. Missing fields are not evidence of zero economic activity.",
            "Accrual changes and booked interest can refer to a different economic period; this bridge describes report-period NAV movements only.",
        ],
    )


def explain_bundle(snapshot_root, output):
    root = Path(snapshot_root)
    snapshot, _, _ = _snapshot(root, datetime.now(timezone.utc))
    raw = (root / "report.xml").read_bytes()
    account = discover_report(raw)["accounts"][0]
    result = explain_nav(
        raw, expected_account=account, base_currency=snapshot["base_currency"]
    )
    if (
        result["period_end"] != snapshot["report_date"]
        or abs(Decimal(result["ending_nav"]) - Decimal(snapshot["nav_bridge"]["nav"]))
        > TOLERANCE
    ):
        raise ValueError("NAV_ENDING_SNAPSHOT_MISMATCH")
    result.update(
        account_ref=snapshot["account_ref"],
        report_sha256=digest(root / "report.xml"),
        snapshot_sha256=digest(root / "snapshot.json"),
    )
    return _save(
        output,
        "nav-bridge.json",
        result,
        [root],
        f"# Reported NAV change\n\nPeriod {result['period_start']}–{result['period_end']}, {result['base_currency']}. NAV change {result['nav_change']}; reported-component residual {result['residual']}. Ending NAV matches the recomputed snapshot. This is reported-field arithmetic, not pure security-price/FX attribution, investment performance validation or execution authorization. MTM may contain FX. Accruals/booked interest need not belong economically to the report period. Detailed fields, omissions and limitations are in nav-bridge.json.\n\n[IBKR field reference]({REFERENCE})",
        f"# 报表净值变动\n\n区间 {result['period_start']}–{result['period_end']}，币种 {result['base_currency']}。净值变化 {result['nav_change']}；列示分项对账剩余差额 {result['residual']}。期末净值与重算快照一致。这里只核对报表字段，不代表股价与汇率的独立归因、投资业绩认证或交易授权。MTM 可能包含汇率影响；应计变化与入账利息未必全部在本区间实际发生。字段、缺项及局限见 nav-bridge.json。\n\n[IBKR 字段说明]({REFERENCE})",
    )
