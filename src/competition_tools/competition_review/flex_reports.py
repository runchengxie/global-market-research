"""Inspect account-bound Flex XML without inventing daily coverage or NAV weights."""

from datetime import date
from decimal import Decimal, InvalidOperation
from .flex_client import FlexError, parse_xml


def report_date(value):
    try:
        if len(value) == 8 and value.isascii() and value.isdigit():
            value = value[:4] + "-" + value[4:6] + "-" + value[6:]
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return value
    except (TypeError, ValueError):
        raise FlexError("FLEX_INVALID_REPORT_DATE") from None


def discover_report(raw):
    root = parse_xml(raw)
    if root.tag != "FlexQueryResponse" or root.get("type") != "AF":
        raise FlexError("FLEX_ACTIVITY_XML_REQUIRED")
    statements = root.findall("./FlexStatements/FlexStatement")
    if not statements or len(statements) > 512:
        raise FlexError("FLEX_EMPTY_OR_OVERSIZED_REPORT")
    accounts = sorted(
        {
            e.get("accountId")
            for e in root.iter()
            if e.get("accountId") and e.get("accountId") != "-"
        }
    )
    if (
        any(not s.get("accountId") or s.get("accountId") == "-" for s in statements)
        or not accounts
    ):
        raise FlexError("FLEX_ACCOUNT_ID_REQUIRED")
    bases = {
        account: sorted(
            {
                e.get("currency")
                for e in root.iter()
                if e.tag in {"AccountInformation", "EquitySummaryByReportDateInBase"}
                and e.get("accountId") == account
                and e.get("currency")
                and len(e.get("currency")) == 3
            }
        )
        for account in accounts
    }
    periods = []
    for s in statements:
        start, end = report_date(s.get("fromDate")), report_date(s.get("toDate"))
        if start > end:
            raise FlexError("FLEX_INVALID_REPORT_PERIOD")
        periods.append(dict(start=start, end=end))
    return dict(accounts=accounts, base_currencies=bases, periods=periods)


def _number(value, *, positive=False, nonnegative=False):
    try:
        n = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise FlexError("FLEX_INVALID_POSITION_NUMBER") from None
    if not n.is_finite() or (positive and n <= 0) or (nonnegative and n < 0):
        raise FlexError("FLEX_INVALID_POSITION_NUMBER")
    return str(n)


def inspect_report(raw, *, expected_account, base_currency, account_ref):
    discovery = discover_report(raw)
    if not expected_account or discovery["accounts"] != [expected_account]:
        raise FlexError("FLEX_ACCOUNT_MISMATCH")
    observed_bases = discovery["base_currencies"][expected_account]
    if len(observed_bases) > 1 or (
        base_currency and observed_bases and observed_bases != [base_currency]
    ):
        raise FlexError("FLEX_BASE_CURRENCY_MISMATCH")
    root = parse_xml(raw)
    sections = {}
    positions = []
    seen = set()
    issues = [] if observed_bases else ["BASE_CURRENCY_UNVERIFIED"]
    for statement in root.findall("./FlexStatements/FlexStatement"):
        start, end = (
            report_date(statement.get("fromDate")),
            report_date(statement.get("toDate")),
        )
        for section in statement:
            info = sections.setdefault(
                section.tag, dict(row_count=0, reported_dates=[])
            )
            info["row_count"] += len(section)
            for row in section:
                if row.get("reportDate"):
                    info["reported_dates"].append(report_date(row.get("reportDate")))
            if section.tag != "OpenPositions":
                continue
            for row in section:
                if (
                    row.get("accountId") == "-"
                    or row.tag != "OpenPosition"
                    or row.get("assetCategory") != "STK"
                    or row.get("levelOfDetail", "").upper() != "SUMMARY"
                ):
                    issues.append("POSITION_ROW_NOT_AGGREGATED")
                    continue
                required = ["reportDate", "symbol", "currency", "position"]
                if any(not row.get(k) for k in required):
                    issues.append("STOCK_ROW_INCOMPLETE")
                    continue
                stamp = report_date(row.get("reportDate"))
                if not start <= stamp <= end:
                    raise FlexError("FLEX_POSITION_DATE_OUTSIDE_REPORT")
                key = (
                    stamp,
                    row.get("conid"),
                    row.get("symbol"),
                    row.get("currency"),
                    row.get("model"),
                )
                if key in seen:
                    raise FlexError("FLEX_DUPLICATE_SUMMARY_POSITION")
                seen.add(key)
                item = dict(
                    report_date=stamp,
                    symbol=row.get("symbol"),
                    conid=row.get("conid"),
                    currency=row.get("currency"),
                    model=row.get("model"),
                    quantity=_number(row.get("position")),
                )
                for source, target, positive in [
                    ("markPrice", "mark_price", False),
                    ("positionValue", "position_value", False),
                    ("multiplier", "multiplier", True),
                    ("fxRateToBase", "fx_rate_to_base", True),
                ]:
                    value = row.get(source)
                    item[target] = (
                        _number(
                            value, positive=positive, nonnegative=source == "markPrice"
                        )
                        if value
                        else None
                    )
                if any(
                    item[k] is None
                    for k in [
                        "mark_price",
                        "position_value",
                        "multiplier",
                        "fx_rate_to_base",
                        "conid",
                    ]
                ):
                    issues.append("STOCK_VALUATION_OR_IDENTITY_INCOMPLETE")
                positions.append(item)
    for info in sections.values():
        info["reported_dates"] = sorted(set(info["reported_dates"]))
    for section in [
        "OpenPositions",
        "Trades",
        "CashTransactions",
        "EquitySummaryInBase",
    ]:
        if section not in sections:
            issues.append("MISSING_SECTION:" + section)
    return dict(
        schema="competition.flex_observation.v1",
        account_ref=account_ref,
        account_match=True,
        platform_account_binding="unverified",
        base_currency=observed_bases[0] if observed_bases else (base_currency or None),
        base_currency_match=True if observed_bases and base_currency else None,
        periods=discovery["periods"],
        sections=sections,
        stock_positions=positions,
        issues=sorted(set(issues)),
        position_values="reported_fields_no_automatic_base_conversion_or_nav_weights",
        coverage="reported_dates_only_not_verified_daily_history",
        official_daily_facts_complete=False,
        official_eligibility="unverified",
        execution_authorized=False,
    )
