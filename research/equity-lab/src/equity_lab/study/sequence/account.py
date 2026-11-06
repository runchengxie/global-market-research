"""Hypothetical split-adjusted price-unit sleeves, with cash-funded fees."""

import math
from itertools import groupby
import numpy as np
from equity_lab.portfolio.cash_rebalance import rebalance


def replay_sequence(observations, fee_bps=5):
    if (
        "prediction" not in observations
        or not np.isin(observations.prediction, [0, 1]).all()
    ):
        raise ValueError("INVALID_POSITION")
    rows = observations.copy()
    rows["allocation"] = rows.prediction.astype(float)
    return replay_allocations(rows, fee_bps)


def replay_allocations(observations, fee_bps=5):
    """Daily-rebalanced sleeve weights in [0,1], not a hindsight match."""
    a = observations.copy().sort_values(["entry_session", "symbol"])
    if a.empty or a.duplicated(["entry_session", "symbol"]).any():
        raise ValueError("INVALID_ACCOUNT_ROWS")
    if "allocation" not in a:
        raise ValueError("INVALID_ALLOCATION")
    allocation = a.allocation.to_numpy(dtype=float)
    if not np.isfinite(allocation).all() or ((allocation < 0) | (allocation > 1)).any():
        raise ValueError("INVALID_ALLOCATION")
    prices = a[["entry_price", "exit_price"]].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("INVALID_ACCOUNT_PRICE")
    symbols = sorted(a.symbol.unique())
    cash = {n: 1 / len(symbols) for n in symbols}
    quantities = {n: {} for n in symbols}
    last = {}
    marks, fills = [], []
    total_cost, turnover = 0.0, 0.0
    for day, iterator in groupby(
        a.itertuples(index=False), key=lambda row: row.entry_session
    ):
        group = list(iterator)
        if (
            sorted(row.symbol for row in group) != symbols
            or len({row.exit_session for row in group}) != 1
        ):
            raise ValueError("INCOMPLETE_ACCOUNT_PANEL")
        for row in group:
            n = row.symbol
            if n in last and (
                last[n][0] != day or not math.isclose(last[n][1], row.entry_price)
            ):
                raise ValueError("DISCONTINUOUS_ACCOUNT_PRICE")
            trade = rebalance(
                cash[n],
                quantities[n],
                {n: float(row.entry_price)},
                {n: float(row.allocation)},
                fee_bps,
            )
            cash[n], quantities[n] = trade["cash"], trade["quantities"]
            if trade["traded"] > 1e-12:
                fills.append(
                    dict(
                        symbol=n,
                        session=day,
                        notional=trade["traded"],
                        cost=trade["cost"],
                    )
                )
            total_cost += trade["cost"]
            turnover += trade["traded"]
            last[n] = (row.exit_session, row.exit_price)
        open_prices = {row.symbol: row.entry_price for row in group}
        open_gross = sum(quantities[n].get(n, 0) * open_prices[n] for n in symbols)
        open_equity = sum(cash.values()) + open_gross
        equity = sum(cash[n] + quantities[n].get(n, 0) * last[n][1] for n in symbols)
        gross = sum(quantities[n].get(n, 0) * last[n][1] for n in symbols)
        marks.append(
            dict(
                date=group[0].exit_session,
                equity=equity,
                cash=sum(cash.values()),
                target_exposure=float(np.mean([row.allocation for row in group])),
                open_exposure=float(open_gross / open_equity),
                marked_exposure=float(gross / equity),
            )
        )
    for n in symbols:
        trade = rebalance(cash[n], quantities[n], {n: float(last[n][1])}, {}, fee_bps)
        cash[n], quantities[n] = trade["cash"], trade["quantities"]
        total_cost += trade["cost"]
        turnover += trade["traded"]
        if trade["traded"] > 1e-12:
            fills.append(
                dict(
                    symbol=n,
                    session=last[n][0],
                    notional=trade["traded"],
                    cost=trade["cost"],
                )
            )
    marks[-1].update(
        equity=sum(cash.values()), cash=sum(cash.values()), marked_exposure=0.0
    )
    equity = np.array([1.0, *[m["equity"] for m in marks]])
    returns = equity[1:] / equity[:-1] - 1
    sd = returns.std(ddof=1) if len(returns) > 1 else 0.0
    return dict(
        return_=float(equity[-1] - 1),
        **{"return": float(equity[-1] - 1)},
        drawdown=float((equity / np.maximum.accumulate(equity) - 1).min()),
        sharpe=float(returns.mean() / sd * np.sqrt(252)) if sd > 0 else None,
        sharpe_reason=None if sd > 0 else "constant_or_insufficient_returns",
        trades=len(fills),
        cost=total_cost,
        turnover=turnover,
        exposure=float(a.allocation.mean()),
        marks=marks,
        fills=fills,
    )
