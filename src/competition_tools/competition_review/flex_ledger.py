"""Reported-day diagnostics, not official rates, current positions or strategy returns."""

from collections import Counter, defaultdict
from decimal import Decimal
from .flex_client import FlexError, parse_xml
from .flex_reports import discover_report, report_date, _number


def summarize_ledger(raw, *, expected_account):
    discovery = discover_report(raw)
    if discovery["accounts"] != [expected_account]:
        raise FlexError("FLEX_ACCOUNT_MISMATCH")
    root = parse_xml(raw)
    navs = {}
    executions = {}
    duplicate_executions = 0
    skipped_levels = Counter()
    issues = []
    cash = defaultdict(Decimal)
    cash_seen = {}
    for statement in root.findall("./FlexStatements/FlexStatement"):
        first, last = (
            report_date(statement.get("fromDate")),
            report_date(statement.get("toDate")),
        )
        for row in statement.findall(
            "./EquitySummaryInBase/EquitySummaryByReportDateInBase"
        ):
            if row.get("accountId") != expected_account:
                continue
            day = report_date(row.get("reportDate"))
            if not first <= day <= last:
                continue  # Prior-period reference NAV is not a contest-day observation.
            if len(row.get("currency", "")) != 3:
                issues.append("NAV_CURRENCY_UNKNOWN")
                continue
            total = Decimal(_number(row.get("total"), positive=True))
            long = Decimal(_number(row.get("stockLong"), nonnegative=True))
            short = Decimal(_number(row.get("stockShort")))
            value = dict(
                report_date=day,
                currency=row.get("currency"),
                nav=str(total),
                stock_gross_value=str(abs(long) + abs(short)),
                stock_exposure_proxy=str((abs(long) + abs(short)) / total),
            )
            if day in navs and navs[day] != value:
                raise FlexError("FLEX_CONFLICTING_DAILY_NAV")
            navs[day] = value
        for row in statement.findall("./Trades/*"):
            if row.tag != "Trade" or row.get("levelOfDetail") != "EXECUTION":
                skipped_levels[row.tag] += 1
                continue
            if row.get("accountId") != expected_account or not row.get("tradeID"):
                raise FlexError("FLEX_EXECUTION_ID_OR_ACCOUNT_MISSING")
            key = row.get("tradeID")
            attrs = dict(row.attrib)
            if key in executions:
                if executions[key] != attrs:
                    raise FlexError("FLEX_CONFLICTING_TRADE_ID")
                duplicate_executions += 1
                continue
            executions[key] = attrs
        for row in statement.findall("./CashTransactions/CashTransaction"):
            if row.get("accountId") != expected_account:
                continue
            key = row.get("transactionID")
            if not key:
                issues.append("CASH_TRANSACTION_ID_MISSING")
                continue
            attrs = dict(row.attrib)
            if key in cash_seen:
                if cash_seen[key] != attrs:
                    raise FlexError("FLEX_CONFLICTING_CASH_ID")
                continue
            cash_seen[key] = attrs
            cash[(row.get("currency"), row.get("type"))] += Decimal(
                _number(row.get("amount"))
            )
    groups = {}
    commissions = defaultdict(Decimal)
    for row in executions.values():
        if row.get("transactionType") != "ExchTrade" or any(
            row.get(k) not in [None, "", "0"]
            for k in [
                "origTradeID",
                "relatedTradeID",
                "origTransactionID",
                "relatedTransactionID",
            ]
        ):
            issues.append("CORRECTION_OR_NONSTANDARD_EXECUTION_REQUIRES_REVIEW")
            continue
        quantity = Decimal(_number(row.get("quantity")))
        if (
            row.get("buySell") not in ["BUY", "SELL"]
            or (row["buySell"] == "BUY" and quantity < 0)
            or (row["buySell"] == "SELL" and quantity > 0)
        ):
            raise FlexError("FLEX_EXECUTION_SIDE_MISMATCH")
        day = report_date(row.get("tradeDate"))
        group_key = (row.get("symbol"), row.get("assetCategory"), row.get("currency"))
        group = groups.setdefault(
            group_key,
            dict(
                symbol=group_key[0],
                asset_class=group_key[1],
                currency=group_key[2],
                execution_count=0,
                signed_execution_quantity=Decimal(0),
                trade_dates=set(),
                order_ids=set(),
            ),
        )
        group["execution_count"] += 1
        group["signed_execution_quantity"] += quantity
        group["trade_dates"].add(day)
        if row.get("ibOrderID"):
            group["order_ids"].add(row["ibOrderID"])
        if row.get("ibCommission") and row.get("ibCommissionCurrency"):
            commissions[row["ibCommissionCurrency"]] += Decimal(
                _number(row["ibCommission"])
            )
    for group in groups.values():
        group["signed_execution_quantity"] = str(group["signed_execution_quantity"])
        group["trade_dates"] = sorted(group["trade_dates"])
        group["order_identifiers"] = len(group.pop("order_ids"))
    rows = sorted(navs.values(), key=lambda r: r["report_date"])
    currencies = {r["currency"] for r in rows}
    if len(currencies) > 1:
        raise FlexError("FLEX_MIXED_NAV_CURRENCIES")
    ratios = [Decimal(r["stock_exposure_proxy"]) for r in rows]
    return dict(
        schema="competition.flex_ledger_diagnostics.v1",
        reported_nav=rows,
        stock_exposure_proxy=dict(
            mean=str(sum(ratios) / len(ratios)) if ratios else None,
            observations=len(ratios),
            scope="reported_dates_only_stock_gross_over_nav_not_official_position_rate",
        ),
        executions=dict(
            unique_records=len(executions),
            duplicate_records=duplicate_executions,
            order_identifiers=len(
                {r["ibOrderID"] for r in executions.values() if r.get("ibOrderID")}
            ),
            skipped_summary_rows=dict(skipped_levels),
            groups=list(groups.values()),
            commissions_by_currency={k: str(v) for k, v in commissions.items()},
        ),
        cash_transactions=dict(
            unique_records=len(cash_seen),
            amounts_by_currency_and_type=[
                dict(currency=k[0], type=k[1], amount=str(v))
                for k, v in sorted(cash.items())
            ],
        ),
        issues=sorted(set(issues)),
        current_positions_reconstructed=False,
        official_eligibility="unverified",
        execution_authorized=False,
    )
