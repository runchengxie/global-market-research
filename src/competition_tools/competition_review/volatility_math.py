"""Narrow USD adjusted-unit volatility-study arithmetic, never an execution ledger."""

import math
from statistics import stdev
from .evidence import aware


def number(value, low=0, high=None, *, positive=False):
    if type(value) not in (int, float):
        raise ValueError("FINITE_NUMERIC_VALUE_REQUIRED")
    n = float(value)
    if (
        not math.isfinite(n)
        or n < low
        or (positive and n <= low)
        or (high is not None and n > high)
    ):
        raise ValueError("NUMBER_OUTSIDE_STUDY_BOUNDS")
    return n


def target_from_closes(prices, lookback, target, cap, annualization):
    if (
        type(lookback) is not int
        or not 2 <= lookback <= 252
        or len(prices) < lookback + 1
    ):
        raise ValueError("INSUFFICIENT_VOL_HISTORY")
    if type(annualization) is not int or annualization <= 0:
        raise ValueError("INVALID_ANNUALIZATION")
    target, cap = (
        number(target, high=1, positive=True),
        number(cap, high=1, positive=True),
    )
    history = [number(v, positive=True) for v in prices[-lookback - 1 :]]
    returns = [b / a - 1 for a, b in zip(history, history[1:])]
    vol = stdev(returns) * math.sqrt(annualization)
    if not math.isfinite(vol) or vol <= 0:
        raise ValueError("ZERO_OR_INVALID_VOLATILITY")
    return dict(
        weight=min(cap, target / vol),
        estimated_volatility=vol,
        return_observations=lookback,
    )


def rebalance(stock, cash, weight, bps):
    stock, cash = number(stock), number(cash)
    weight, fee = number(weight, high=1), number(bps, high=100) / 10000
    nav = stock + cash
    if nav <= 0:
        raise ValueError("NONPOSITIVE_STUDY_NAV")
    delta = weight * nav - stock
    cost = fee * abs(delta) / (1 + fee * weight if delta >= 0 else 1 - fee * weight)
    after = nav - cost
    return weight * after, (1 - weight) * after, cost


def simulate(points, bps, *, fixed_weight=None, buffer=0, annualization=252):
    number(bps, high=100)
    buffer = number(buffer, high=1)
    if fixed_weight is not None:
        fixed_weight = number(fixed_weight, high=1)
    if type(annualization) is not int or annualization <= 0 or len(points) < 2:
        raise ValueError("INVALID_STUDY_LENGTH_OR_ANNUALIZATION")
    clocks = [aware(p["at"]) for p in points]
    for i, p in enumerate(points):
        number(p["price"], positive=True)
        number(p["target"], high=1)
        if type(p["rebalance"]) is not bool:
            raise ValueError("REBALANCE_FLAG_REQUIRED")
        if aware(p["signal_at"]) >= clocks[i] or (i and clocks[i] <= clocks[i - 1]):
            raise ValueError("NONCAUSAL_OR_UNORDERED_STUDY_CLOCK")
    units, cash, peak = 0.0, 1.0, 1.0
    path, transactions = [], []
    for i, p in enumerate(points):
        stock = units * p["price"]
        before = stock + cash
        if not math.isfinite(before) or before <= 0:
            raise ValueError("NONPOSITIVE_STUDY_NAV")
        terminal = i == len(points) - 1
        desired = (
            0 if terminal else p["target"] if fixed_weight is None else fixed_weight
        )
        change = (
            terminal
            or i == 0
            or (p["rebalance"] and abs(desired - stock / before) > buffer + 1e-12)
        )
        if change:
            after_stock, cash, cost = rebalance(stock, cash, desired, bps)
            if abs(after_stock - stock) > 1e-12:
                transactions.append(
                    dict(
                        at=p["at"],
                        signal_at=p["signal_at"] if not terminal else None,
                        terminal=terminal,
                        stock_change=after_stock - stock,
                        cost=cost,
                        turnover=abs(after_stock - stock) / before,
                        target=desired,
                        pre_trade_nav=before,
                    )
                )
            stock = after_stock
            units = stock / p["price"]
        nav = stock + cash
        peak = max(peak, nav)
        path.append(
            dict(
                at=p["at"],
                nav=nav,
                stock_value=stock,
                cash=cash,
                exposure=stock / nav,
                drawdown=nav / peak - 1,
            )
        )
    final = path[-1]["nav"]
    days = (clocks[-1] - clocks[0]).total_seconds() / 86400
    daily = [
        path[i]["nav"] / (1 if i == 1 else path[i - 1]["nav"]) - 1
        for i in range(1, len(path))
    ]
    return dict(
        path=path,
        transactions=transactions,
        metrics=dict(
            total_return=final - 1,
            cagr=final ** (365.25 / days) - 1,
            realized_volatility=stdev(daily) * math.sqrt(annualization)
            if len(daily) > 1
            else None,
            maximum_drawdown=min(r["drawdown"] for r in path),
            mean_exposure=sum(r["exposure"] for r in path[:-1]) / (len(path) - 1),
            initial_nav_costs=sum(r["cost"] for r in transactions),
            sum_trade_turnover=sum(r["turnover"] for r in transactions),
            transaction_count=len(transactions),
            intervals=len(path) - 1,
        ),
    )


def match_fixed(points, bps, mean_exposure, *, tolerance=1e-7, annualization=252):
    desired = number(mean_exposure, high=1)
    tolerance = number(tolerance, high=1e-4, positive=True)
    low, high = 0.0, 1.0
    for _ in range(50):
        weight = (low + high) / 2
        result = simulate(points, bps, fixed_weight=weight, annualization=annualization)
        residual = result["metrics"]["mean_exposure"] - desired
        if abs(residual) <= tolerance:
            return dict(
                fixed_weight=weight,
                residual=residual,
                hindsight_nontradable=True,
                matching_scope="mean_actual_post_trade_pre_interval_stock_weight",
                result=result,
            )
        if residual < 0:
            low = weight
        else:
            high = weight
    raise ValueError("MEAN_EXPOSURE_MATCH_NOT_WITHIN_TOLERANCE")
