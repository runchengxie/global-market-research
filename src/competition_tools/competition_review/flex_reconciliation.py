"""Observed stock/cash valuation checks; never target construction or eligibility."""

from decimal import Decimal, DecimalException
import re
from .flex_client import FlexError, parse_xml
from .flex_reports import inspect_report, report_date, _number

LOCAL_TOLERANCE = Decimal("0.01")
BASE_TOLERANCE = Decimal("0.02")
FX_TOLERANCE = Decimal("0.00000001")
OTHER_ASSETS = [
    "options",
    "bonds",
    "notes",
    "funds",
    "commodities",
    "crypto",
    "slbCashCollateral",
    "slbDirectSecuritiesBorrowed",
    "slbDirectSecuritiesLent",
    "softDollars",
    "physDel",
    "cfdUnrealizedPl",
    "forexCfdUnrealizedPl",
    "ipoSubscription",
    "incentiveCouponAccruals",
]


def _d(value):
    return Decimal(_number(value))


def _rates(root, day, base):
    result = {base: Decimal(1)}
    for row in root.iter("ConversionRate"):
        if row.get("toCurrency") != base or not row.get("reportDate"):
            continue
        if report_date(row.get("reportDate")) != day:
            continue
        currency = row.get("fromCurrency")
        value = Decimal(_number(row.get("rate"), positive=True))
        if currency in result and result[currency] != value:
            raise FlexError("CONFLICTING_SAME_DAY_FX")
        result[currency] = value
    return result


def _stocks(positions, day, nav, rates, base):
    result = dict(
        status="blocked",
        positions=[],
        value_base=None,
        gross_value_base=None,
        issues=[],
    )
    try:
        selected = [p for p in positions if p["report_date"] == day]
        if not selected:
            raise FlexError("NO_STOCK_SUMMARY_ON_NAV_DATE")
        net = Decimal(0)
        gross = Decimal(0)
        identities = set()
        for p in selected:
            if (
                not re.fullmatch(r"[1-9][0-9]{0,19}", p["conid"] or "")
                or p["conid"] in identities
            ):
                raise FlexError("STOCK_CONTRACT_IDENTITY_AMBIGUOUS")
            identities.add(p["conid"])
            if (
                not p["conid"]
                or p["model"]
                or any(
                    p[k] is None
                    for k in [
                        "mark_price",
                        "position_value",
                        "multiplier",
                        "fx_rate_to_base",
                    ]
                )
            ):
                raise FlexError("STOCK_IDENTITY_MARK_OR_MODEL_SCOPE_INVALID")
            local = _d(p["quantity"]) * _d(p["mark_price"]) * _d(p["multiplier"])
            if abs(local - _d(p["position_value"])) > LOCAL_TOLERANCE:
                raise FlexError("LOCAL_MARK_VALUE_MISMATCH")
            fx = _d(p["fx_rate_to_base"])
            if p["currency"] == base and fx != 1:
                raise FlexError("BASE_CURRENCY_FX_NOT_ONE")
            if p["currency"] in rates and abs(
                fx - rates[p["currency"]]
            ) > FX_TOLERANCE * max(abs(fx), Decimal(1)):
                raise FlexError("POSITION_FX_RATE_MISMATCH")
            value = _d(p["position_value"]) * fx
            item = {
                k: p[k]
                for k in [
                    "conid",
                    "symbol",
                    "currency",
                    "quantity",
                    "mark_price",
                    "multiplier",
                    "position_value",
                    "fx_rate_to_base",
                ]
            }
            item.update(value_base=str(value), observed_weight=None)
            result["positions"].append(item)
            net += value
            gross += abs(value)
        nav_net = _d(nav.get("stock"))
        nav_gross = abs(_d(nav.get("stockLong"))) + abs(_d(nav.get("stockShort")))
        if (
            abs(net - nav_net) > BASE_TOLERANCE
            or abs(gross - nav_gross) > BASE_TOLERANCE
        ):
            raise FlexError("STOCK_NAV_VALUE_MISMATCH")
        total = Decimal(_number(nav.get("total"), positive=True))
        for item in result["positions"]:
            item["observed_weight"] = str(_d(item["value_base"]) / total)
        result.update(
            status="reconciled",
            value_base=str(net),
            gross_value_base=str(gross),
            reported_nav_stock=str(nav_net),
            reported_nav_stock_gross=str(nav_gross),
        )
    except (FlexError, DecimalException) as exc:
        result["issues"].append(
            str(exc)
            if isinstance(exc, FlexError)
            else "NUMERIC_ARITHMETIC_OUT_OF_RANGE"
        )
        for item in result["positions"]:
            item["observed_weight"] = None
    return result


def _cash(root, day, nav, rates, expected):
    result = dict(status="blocked", balances=[], value_base=None, issues=[])
    try:
        balances = {}
        for statement in root.findall("./FlexStatements/FlexStatement"):
            first, last = (
                report_date(statement.get("fromDate")),
                report_date(statement.get("toDate")),
            )
            for row in statement.findall("./CashReport/CashReportCurrency"):
                if (
                    row.get("currency") == "BASE_SUMMARY"
                    or row.get("levelOfDetail") != "Currency"
                ):
                    continue
                end = report_date(row.get("toDate"))
                if end != day:
                    continue
                if not first <= report_date(row.get("fromDate")) <= end <= last:
                    raise FlexError("CASH_DATE_OUTSIDE_REPORT")
                if row.get("accountId") != expected or row.get("model"):
                    raise FlexError("CASH_ACCOUNT_OR_MODEL_SCOPE_INVALID")
                currency = row.get("currency")
                if not re.fullmatch(r"[A-Z]{3}", currency or ""):
                    raise FlexError("CASH_CURRENCY_UNSUPPORTED")
                amount = _d(row.get("endingCash"))
                if currency in balances and balances[currency] != amount:
                    raise FlexError("CONFLICTING_CURRENCY_CASH")
                balances[currency] = amount
        if not balances:
            raise FlexError("NO_CURRENCY_CASH_ON_NAV_DATE")
        total = Decimal(0)
        for currency, amount in sorted(balances.items()):
            item = dict(
                currency=currency,
                amount=str(amount),
                fx_rate_to_base=None,
                value_base=None,
            )
            result["balances"].append(item)
            if currency not in rates:
                continue
            item.update(
                fx_rate_to_base=str(rates[currency]),
                value_base=str(amount * rates[currency]),
            )
            total += amount * rates[currency]
        if any(item["value_base"] is None for item in result["balances"]):
            raise FlexError("SAME_DAY_CASH_FX_MISSING")
        reported = _d(nav.get("cash"))
        if abs(total - reported) > BASE_TOLERANCE:
            raise FlexError("CASH_NAV_VALUE_MISMATCH")
        result.update(
            status="reconciled", value_base=str(total), reported_nav_cash=str(reported)
        )
    except (FlexError, DecimalException) as exc:
        result["issues"].append(
            str(exc)
            if isinstance(exc, FlexError)
            else "NUMERIC_ARITHMETIC_OUT_OF_RANGE"
        )
    return result


def reconcile_snapshot(raw, *, expected_account, base_currency, account_ref):
    observation = inspect_report(
        raw,
        expected_account=expected_account,
        base_currency=base_currency,
        account_ref=account_ref,
    )
    root = parse_xml(raw)
    base = observation["base_currency"]
    nav_rows = {}
    global_issues = []
    for statement in root.findall("./FlexStatements/FlexStatement"):
        first, last = (
            report_date(statement.get("fromDate")),
            report_date(statement.get("toDate")),
        )
        for row in statement.findall(
            "./EquitySummaryInBase/EquitySummaryByReportDateInBase"
        ):
            if row.get("accountId") != expected_account or row.get("currency") != base:
                continue
            day = report_date(row.get("reportDate"))
            if day < first:
                continue
            if day > last:
                global_issues.append("NAV_DATE_AFTER_REPORT")
                continue
            attrs = dict(row.attrib)
            if row.get("model"):
                global_issues.append("NAV_MODEL_SCOPE_UNSUPPORTED")
            if day in nav_rows and nav_rows[day] != attrs:
                global_issues.append("CONFLICTING_NAV_ROW")
            nav_rows[day] = attrs
    dates = [*nav_rows, *[p["report_date"] for p in observation["stock_positions"]]]
    day = max(dates) if dates else None
    result = dict(
        schema="competition.flex_snapshot.v1",
        account_ref=account_ref,
        report_date=day,
        base_currency=base,
        scope="reported_stock_cash_accrual_components_only",
        status="needs_review",
        stock=dict(status="blocked", positions=[], value_base=None, issues=[]),
        cash=dict(status="blocked", balances=[], value_base=None, issues=[]),
        nav_bridge=dict(status="unavailable", residual=None),
        unsupported_nav_assets=[],
        issues=global_issues,
        tolerances=dict(
            local_value=str(LOCAL_TOLERANCE),
            base_value=str(BASE_TOLERANCE),
            fx_relative_floor_one=str(FX_TOLERANCE),
        ),
        official_eligibility="unverified",
        platform_account_binding="unverified",
        execution_authorized=False,
    )
    if global_issues or day not in nav_rows or not base:
        result["issues"].append("MATCHING_LATEST_NAV_REQUIRED")
        return result
    nav = nav_rows[day]
    try:
        rates = _rates(root, day, base)
        result["stock"] = _stocks(observation["stock_positions"], day, nav, rates, base)
        result["cash"] = _cash(root, day, nav, rates, expected_account)
        total = Decimal(_number(nav.get("total"), positive=True))
        components = {
            k: _d(nav.get(k))
            for k in ["stock", "cash", "interestAccruals", "dividendAccruals"]
        }
        residual = total - sum(components.values())
        result["nav_bridge"] = dict(
            status="reconciled_core_components"
            if abs(residual) <= BASE_TOLERANCE
            else "unexplained_residual",
            nav=str(total),
            components={k: str(v) for k, v in components.items()},
            residual=str(residual),
        )
        result["unsupported_nav_assets"] = [
            k for k in OTHER_ASSETS if nav.get(k) not in [None, ""] and _d(nav[k]) != 0
        ]
        if (
            result["stock"]["status"] == result["cash"]["status"] == "reconciled"
            and abs(residual) <= BASE_TOLERANCE
            and not result["unsupported_nav_assets"]
        ):
            result["status"] = "reconciled_stock_cash"
    except (FlexError, DecimalException) as exc:
        result["issues"].append(
            str(exc)
            if isinstance(exc, FlexError)
            else "NUMERIC_ARITHMETIC_OUT_OF_RANGE"
        )
    return result
