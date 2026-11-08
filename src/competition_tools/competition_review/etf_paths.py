"""Constant-unit retrospective marked paths, not an actual account or execution ledger."""

from decimal import Decimal
from .participation import decimal
from .etf_rehearsal import positive
from .evidence import aware


def path_metrics(reference, weights, marks, cost_bps, cash_rate):
    """SGD residual simple ACT/365 accrual; fees at entry, no terminal liquidation."""
    if not reference or len(marks) < 2 or set(weights) - set(reference):
        raise ValueError("INVALID_PATH_ASSETS_OR_LENGTH")
    ref = {k: decimal(v) for k, v in reference.items()}
    target = {k: decimal(v) for k, v in weights.items()}
    if sum(ref.values()) > 1 or sum(target.values()) > 1:
        raise ValueError("UNLEVERED_PATH_REQUIRED")
    fee, rate = decimal(cost_bps), decimal(cash_rate)
    if fee > 10000 or rate > 1:
        raise ValueError("INVALID_PATH_COST_OR_CASH_RATE")
    turnover = sum(abs(target.get(k, Decimal(0)) - ref[k]) for k in ref)
    cost = turnover * fee / 10000
    cash = 1 - sum(target.values()) - cost
    if cash < 0:
        raise ValueError("INITIAL_COST_NOT_CASH_FUNDED")
    clocks = [aware(r["endpoint"]) for r in marks]
    if any(b <= a for a, b in zip(clocks, clocks[1:])):
        raise ValueError("UNORDERED_PATH_MARKS")
    prices = []
    for row in marks:
        if set(row["base_values"]) != set(ref):
            raise ValueError("PATH_MARK_IDENTITY_MISMATCH")
        prices.append({k: positive(v) for k, v in row["base_values"].items()})
    peak = Decimal(1)  # Pre-cost initial wealth is part of drawdown history.
    path = []
    for at, values in zip(clocks, prices):
        elapsed = Decimal(str((at - clocks[0]).total_seconds())) / Decimal(86400)
        cash_value = cash * (1 + rate * elapsed / 365)
        stock_value = sum(
            (w * values[k] / prices[0][k] for k, w in target.items()), Decimal(0)
        )
        nav = stock_value + cash_value
        if nav <= 0:
            raise ValueError("NONPOSITIVE_PATH_NAV")
        peak = max(peak, nav)
        path.append(
            dict(
                at=at.isoformat(),
                nav=str(nav),
                drawdown=str(nav / peak - 1),
                stock_value=str(stock_value),
                modeled_cash=str(cash_value),
            )
        )
    return dict(
        cash_annual_rate=str(rate),
        cash_model="simple_ACT_365_elapsed_UTC_after_entry_fee",
        path=path,
        return_after_initial_cost=str(Decimal(path[-1]["nav"]) - 1),
        maximum_drawdown=str(min(Decimal(r["drawdown"]) for r in path)),
        initial_stock_turnover=str(turnover),
        initial_cost_fraction=str(cost),
        samples=len(path),
        risk_scope="opening_marks_only_not_intraday_or_close_drawdown",
    )
