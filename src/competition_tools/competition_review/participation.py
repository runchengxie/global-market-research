"""Elapsed-session participation arithmetic; not official qualification scoring."""

from datetime import date
from decimal import Decimal, InvalidOperation


def decimal(value):
    if type(value) not in [str, int, float, Decimal]:
        raise ValueError("INVALID_NUMBER")
    try:
        r = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("INVALID_NUMBER") from exc
    if not r.is_finite() or r < 0:
        raise ValueError("INVALID_NONNEGATIVE_NUMBER")
    return r


def daily_rows(sessions, facts):
    if len(set(sessions)) != len(sessions) or sorted(sessions) != sessions:
        raise ValueError("INVALID_SESSION_LABELS")
    for s in sessions:
        date.fromisoformat(s)
    mapping = {}
    for row in facts:
        key = row["session_date"]
        date.fromisoformat(key)
        if key in mapping:
            raise ValueError("DUPLICATE_SESSION_FACTS")
        for flag in ["complete_day", "had_any_position", "had_any_trade"]:
            if row.get(flag) is not None and type(row[flag]) is not bool:
                raise ValueError("INVALID_DAY_FLAG")
        for metric in ["position_rate", "turnover_rate"]:
            if row.get(metric) is not None:
                decimal(row[metric])
        if row.get("complete_day") is True:
            if (
                row.get("had_any_position") is False
                and row.get("position_rate") is not None
                and decimal(row["position_rate"]) > 0
            ):
                raise ValueError("CONTRADICTORY_POSITION")
            if (
                row.get("had_any_trade") is False
                and row.get("turnover_rate") is not None
                and decimal(row["turnover_rate"]) > 0
            ):
                raise ValueError("CONTRADICTORY_TRADES")
        mapping[key] = row
    out = []
    for s in sessions:
        r = mapping.get(s, {})
        complete = r.get("complete_day") is True
        flat = None
        if (
            complete
            and r.get("had_any_position") is not None
            and r.get("had_any_trade") is not None
        ):
            flat = not (r["had_any_position"] or r["had_any_trade"])
        out.append(
            dict(
                session_date=s,
                position_rate=str(decimal(r["position_rate"]))
                if complete and r.get("position_rate") is not None
                else None,
                turnover_rate=str(decimal(r["turnover_rate"]))
                if complete and r.get("turnover_rate") is not None
                else None,
                flat_day=flat,
                evidence="complete_declared_day" if complete else "unknown_or_partial",
            )
        )
    return out


def summarize_days(rows):
    if not rows:
        raise ValueError("EMPTY_ELAPSED_SESSIONS")
    n = len(rows)
    positions = [
        decimal(r["position_rate"]) for r in rows if r["position_rate"] is not None
    ]
    turnover = [
        decimal(r["turnover_rate"]) for r in rows if r["turnover_rate"] is not None
    ]
    flats = [r["flat_day"] for r in rows if r["flat_day"] is not None]
    mean_position = sum(positions) / n if len(positions) == n else None
    mean_turnover = sum(turnover) / n if len(turnover) == n else None
    a = (
        "unknown"
        if mean_position is None or len(flats) != n
        else "met"
        if mean_position >= Decimal(".5") and sum(flats) <= 10
        else "not_met"
    )
    if sum(flats) > 10 or (mean_position is not None and mean_position < Decimal(".5")):
        a = "not_met"
    b = (
        "unknown"
        if mean_turnover is None
        else "met"
        if mean_turnover >= 1
        else "not_met"
    )
    overall = (
        "met" if "met" in [a, b] else "not_met" if a == b == "not_met" else "unknown"
    )
    return dict(
        scope="elapsed_sessions_only",
        elapsed_sessions=n,
        known_position_days=len(positions),
        known_turnover_days=len(turnover),
        known_flat_status_days=len(flats),
        known_flat_days=sum(flats),
        mean_position_rate=str(mean_position) if mean_position is not None else None,
        mean_turnover_rate=str(mean_turnover) if mean_turnover is not None else None,
        known_position_sum=str(sum(positions)),
        path_a_under_inputs=a,
        path_b_under_inputs=b,
        eligibility_under_inputs=overall,
        official_eligibility="unverified",
    )


def future_bounds(known_sum, known_days, unknown_past, remaining):
    if any(type(x) is not int or x < 0 for x in [known_days, unknown_past, remaining]):
        raise ValueError("INVALID_DAY_COUNT")
    known_sum = decimal(known_sum)
    if known_sum > known_days:
        raise ValueError("UNLEVERED_PLANNING_ONLY")
    if not remaining:
        return dict(
            status="no_future_sessions",
            minimum_required_future_mean=None,
            maximum_required_future_mean=None,
        )
    target = Decimal(".5") * (known_days + unknown_past + remaining)
    lower = max(Decimal(0), (target - known_sum - unknown_past) / remaining)
    upper = max(Decimal(0), (target - known_sum) / remaining)
    return dict(
        status="conditional_planning_only",
        assumption="unknown_and_future_daily_position_bounded_0_1",
        minimum_required_future_mean=str(lower),
        maximum_required_future_mean=str(upper),
        guaranteed_feasible_under_assumption=upper <= 1,
        trade_instruction=False,
    )
