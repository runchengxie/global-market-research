"""Offline adjusted-price-unit diagnostics, never broker shares or account targets."""

import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path

from equity_lab.portfolio.cash_rebalance import rebalance


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _day(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("INVALID_SESSION_DATE")
    return value


def _validate(panel, target, policy, fee_bps, threshold):
    if (
        not isinstance(panel, list)
        or len(panel) < 2
        or not isinstance(target, dict)
        or not target
        or any(not isinstance(n, str) or not n or n == "_cash" for n in target)
        or any(not _number(v) or not 0 <= v <= 1 for v in target.values())
        or sum(target.values()) > 1
        or policy not in ("hold", "monthly", "drift")
        or not _number(fee_bps)
        or not 0 <= fee_bps <= 100
        or not _number(threshold)
        or not 0 < threshold <= 1
    ):
        raise ValueError("INVALID_STATIC_SETTINGS")
    names = None
    previous = ""
    for row in panel:
        if not isinstance(row, dict) or set(row) != {"date", "open", "close"}:
            raise ValueError("INVALID_PANEL_ROW")
        day = _day(row["date"])
        if day <= previous:
            raise ValueError("UNORDERED_SESSION_PANEL")
        previous = day
        for field in ("open", "close"):
            prices = row[field]
            if (
                not isinstance(prices, dict)
                or not prices
                or any(not isinstance(n, str) or not n or n == "_cash" for n in prices)
                or any(not _number(v) or v <= 0 for v in prices.values())
            ):
                raise ValueError("INVALID_PANEL_PRICE")
            if names is None:
                names = set(prices)
            if set(prices) != names or not set(target) <= names:
                raise ValueError("INCOMPLETE_SESSION_PANEL")


def replay(panel, target, policy, fee_bps, threshold=0.05):
    """Calendar-known monthly or prior-close drift decisions, next-open trades.

    Panel completeness against an exchange calendar and adjusted-unit provenance
    are caller responsibilities. No source is accepted as executable pricing.
    """
    _validate(panel, target, policy, fee_bps, threshold)
    cash, quantities = 1.0, {}
    marks, trades = [], []
    previous_weights = None
    names = sorted(target)
    target_all = {**target, "_cash": 1 - sum(target.values())}
    total_cost = total_traded = 0.0
    # Mark initial capital AND opening fee losses before the first closing mark.
    path = [1.0]
    stock_exposures = []
    for i, row in enumerate(panel):
        day = row["date"]
        reason = None
        if i == 0:
            reason = "entry"
        elif policy == "monthly" and day[:7] != panel[i - 1]["date"][:7]:
            reason = "month_boundary"
        elif policy == "drift" and any(
            abs(previous_weights[n] - target_all[n]) >= threshold - 1e-12
            for n in target_all
        ):
            reason = "prior_close_drift"
        if reason:
            trade = rebalance(cash, quantities, row["open"], target, fee_bps)
            cash, quantities = trade["cash"], trade["quantities"]
            total_cost += trade["cost"]
            total_traded += trade["traded"]
            if trade["traded"] > 1e-12:
                trades.append(dict(date=day, reason=reason, **trade))
        open_equity = cash + math.fsum(
            q * row["open"][n] for n, q in quantities.items()
        )
        path.append(open_equity)
        open_weights = {
            n: quantities.get(n, 0) * row["open"][n] / open_equity for n in names
        }
        stock_exposures.append(open_weights)
        equity = cash + math.fsum(q * row["close"][n] for n, q in quantities.items())
        previous_weights = {
            n: quantities.get(n, 0) * row["close"][n] / equity for n in names
        }
        previous_weights["_cash"] = cash / equity
        marks.append(
            dict(
                date=day,
                equity=equity,
                cash=cash,
                weights=dict(previous_weights),
                open_weights=open_weights,
            )
        )
        path.append(equity)
    trade = rebalance(cash, quantities, panel[-1]["close"], {}, fee_bps)
    total_cost += trade["cost"]
    total_traded += trade["traded"]
    if trade["traded"] > 1e-12:
        trades.append(dict(date=panel[-1]["date"], reason="terminal", **trade))
    terminal_cash = trade["cash"]
    # Preserve pre-liquidation holdings but record the charged ending equity.
    marks[-1]["equity"] = terminal_cash
    marks[-1]["terminal_cost"] = trade["cost"]
    path.append(terminal_cash)
    peak, drawdown = 1.0, 0.0
    for value in path:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("INVALID_REPLAY_EQUITY")
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    returns = []
    previous = 1.0
    annual = {}
    for mark in marks:
        returns.append(mark["equity"] / previous - 1)
        year = int(mark["date"][:4])
        group = annual.setdefault(
            year,
            dict(
                year=year, start=mark["date"], starting_equity=previous, observations=0
            ),
        )
        group.update(end=mark["date"], ending_equity=mark["equity"])
        group["observations"] += 1
        group["return"] = group["ending_equity"] / group["starting_equity"] - 1
        previous = mark["equity"]
    mean = math.fsum(returns) / len(returns)
    variance = math.fsum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return dict(
        return_=terminal_cash - 1,
        **{"return": terminal_cash - 1},
        drawdown=drawdown,
        annualized_volatility=math.sqrt(variance * 252),
        mean_open_weights={
            n: math.fsum(w[n] for w in stock_exposures) / len(panel) for n in names
        },
        mean_close_cash_weight=math.fsum(m["weights"]["_cash"] for m in marks)
        / len(panel),
        cost=total_cost,
        traded_initial_capital=total_traded,
        terminal_cash=terminal_cash,
        marks=marks,
        trades=trades,
        annual=list(annual.values()),
    )


def study(panel, protocol):
    if (
        not isinstance(protocol, dict)
        or protocol.get("schema") != "equity.static_allocation_protocol.v1"
        or protocol.get("currency") != "USD"
        or protocol.get("cash_yield") != 0
        or type(protocol.get("cash_yield")) not in (int, float)
        or protocol.get("policies") != ["hold", "monthly", "drift"]
        or protocol.get("fees_bps") != [0, 10, 25]
        or any(type(v) not in (int, float) for v in protocol.get("fees_bps", []))
        or not isinstance(protocol.get("targets"), dict)
        or not protocol["targets"]
        or not isinstance(panel, list)
        or len(panel) < 2
    ):
        raise ValueError("INVALID_STUDY_PROTOCOL")
    if panel[0].get("date") != _day(protocol["start"]) or panel[-1].get("date") != _day(
        protocol["end"]
    ):
        raise ValueError("STUDY_PERIOD_MISMATCH")
    cases = []
    for name, target in protocol["targets"].items():
        if not isinstance(name, str) or not name:
            raise ValueError("INVALID_ARM_NAME")
        for policy in protocol["policies"]:
            for fee in protocol["fees_bps"]:
                cases.append(
                    dict(
                        arm=name,
                        policy=policy,
                        fee_bps=fee,
                        **replay(panel, target, policy, fee, protocol["threshold"]),
                    )
                )
    return dict(
        schema="equity.static_allocation_study.v1",
        protocol=protocol,
        execution_authorized=False,
        adoption_decision="not_evaluated",
        cases=cases,
        limitations=[
            "USD adjusted price units, zero cash yield; not executable shares or dated dividend cash.",
            "Caller verifies calendar completeness, source provenance and consistent adjustment factors.",
            "One provider is not independent price/corporate-action or point-in-time acceptance.",
            "Same stock target is not equal realized exposure or equal portfolio risk.",
            "No actual account FX, taxes, borrowing, lot sizes or broker reconciliation.",
            "Annual returns split one continuous path; first/last years may be partial.",
            "Drawdown uses sampled opens/closes, not intraday extrema; volatility uses daily closes.",
            "Final mark equity includes liquidation cost; its weights/cash describe pre-liquidation holdings.",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw, config = args.input.read_bytes(), args.protocol.read_bytes()
    result = study(json.loads(raw), json.loads(config))
    result.update(
        input_sha256=hashlib.sha256(raw).hexdigest(),
        protocol_sha256=hashlib.sha256(config).hexdigest(),
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
