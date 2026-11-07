"""Completed-bar features, explicitly assumed factor delays and purged splits."""

from bisect import bisect_right
from datetime import timedelta
import numpy as np
from .inputs import instant

NAMES = [
    "return_1bar",
    "return_24h",
    "return_168h",
    "volatility_24h",
    "range_close",
    "volume_ratio_24h",
    "asset_eth",
]
ARMS = {
    "price_only": None,
    "factor_proxy_24h": 24,
    "factor_delayed_72h": 72,
    "factor_shift_7d": 192,
}


def price_features(rows, step):
    if step not in [1, 4]:
        raise ValueError("UNSUPPORTED_GRAIN")
    close = np.array([r["close"] for r in rows])
    volume = np.array([r["volume"] for r in rows])
    returns = np.diff(close) / close[:-1]
    day, week = 24 // step, 168 // step
    out = []
    for i, r in enumerate(rows):
        if i < week:
            out.append(None)
            continue
        average = float(volume[i - day + 1 : i + 1].mean())
        if average <= 0:
            raise ValueError("INVALID_VOLUME_FEATURE")
        out.append(
            [
                close[i] / close[i - 1] - 1,
                close[i] / close[i - day] - 1,
                close[i] / close[i - week] - 1,
                float(returns[i - day : i].std()),
                (r["high"] - r["low"]) / r["close"],
                volume[i] / average - 1,
                float(r["asset"] == "ETHUSDT"),
            ]
        )
    return out


def factor_at(rows, cutoff, delay_hours):
    end = cutoff - timedelta(hours=delay_hours)
    index = bisect_right([r["period_end"] for r in rows], end) - 1
    if index < 0 or end - rows[index]["period_end"] >= timedelta(days=1):
        return None
    return rows[index]["value"]


def split_indices(times, step, test_start, test_end):
    fit = [i for i, t in enumerate(times) if t + timedelta(hours=2 * step) < test_start]
    test = [i for i, t in enumerate(times) if test_start <= t < test_end]
    return np.array(fit, dtype=int), np.array(test, dtype=int)


def samples(rows, step, factors, indicators):
    features = price_features(rows, step)
    result = []
    for i in range(len(rows) - 2):
        if features[i] is None:
            continue
        t = instant(rows[i]["interval_end"])
        arms = {}
        missing = False
        for name, delay in ARMS.items():
            values = (
                []
                if delay is None
                else [
                    factor_at(factors[(rows[i]["asset"], indicator)], t, delay)
                    for indicator in indicators
                ]
            )
            if any(v is None for v in values):
                missing = True
                break
            arms[name] = features[i] + values
        if missing:
            continue
        entry, exit = (
            rows[i + 2]["open"],
            rows[i + 3]["open"] if i + 3 < len(rows) else None,
        )
        # row i closes at t; row i+1 opens at t; one full-bar delay enters i+2.
        if exit is None:
            continue
        result.append(
            dict(
                asset=rows[i]["asset"],
                time=t,
                entry_time=t + timedelta(hours=step),
                exit_time=t + timedelta(hours=2 * step),
                entry=entry,
                exit=exit,
                target=exit / entry - 1,
                features=arms,
            )
        )
    if any(
        b["time"] - a["time"] != timedelta(hours=step)
        for a, b in zip(result, result[1:])
    ):
        raise ValueError("COMMON_SAMPLE_GRID_GAP")
    return result
