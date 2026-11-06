"""Frozen validation choices and causal controls, never test-period targeting."""

import numpy as np
import pandas as pd
from .account import replay_allocations
from .metrics import classification

THRESHOLDS = [0.35, 0.425, 0.5, 0.575, 0.65]


def score_diagnostics(y, p):
    p = np.asarray(p, dtype=float)
    result = classification(y, p)
    result.update(
        base_rate=float(np.mean(y)),
        count=len(p),
        above_cutoff=int((p > 0.5).sum()),
        score_min=float(p.min()),
        score_max=float(p.max()),
        quantiles=dict(
            zip(
                ["0", "5", "25", "50", "75", "95", "100"],
                np.quantile(p, [0, 0.05, 0.25, 0.5, 0.75, 0.95, 1]).tolist(),
            )
        ),
    )
    result["expected_calibration_error"] = sum(
        b["count"] / len(p) * abs(b["predicted"] - b["observed"])
        for b in result["reliability"]
        if b["count"]
    )
    return result


def daily_returns(account):
    equity = np.array([1.0, *[m["equity"] for m in account["marks"]]])
    return equity[1:] / equity[:-1] - 1


def realized_volatility(account):
    r = daily_returns(account)
    return float(r.std(ddof=1) * np.sqrt(252)) if len(r) > 1 else 0.0


def choose_threshold(validation):
    grid = []
    for threshold in THRESHOLDS:
        rows = validation.copy()
        rows["allocation"] = (rows.probability > threshold).astype(float)
        account = replay_allocations(rows, 5)
        grid.append(
            dict(
                threshold=threshold,
                validation_mean_net_return=float(daily_returns(account).mean()),
                trades=account["trades"],
            )
        )
    best = max(
        grid,
        key=lambda r: (
            r["validation_mean_net_return"],
            -abs(r["threshold"] - 0.5),
            r["threshold"],
        ),
    )
    return best["threshold"], grid


def validation_controls(validation):
    rows = validation.copy()
    rows["allocation"] = (rows.probability > 0.5).astype(float)
    model = replay_allocations(rows, 5)
    rows["allocation"] = 1.0
    holding = replay_allocations(rows, 5)
    reference = realized_volatility(holding)
    return dict(
        exposure=model["exposure"],
        volatility=min(realized_volatility(model) / reference, 1.0)
        if reference > 0
        else 0.0,
        volatility_reason=None if reference > 0 else "zero_reference_volatility",
        validation_model_volatility=realized_volatility(model),
        validation_holding_volatility=reference,
    )


def causal_volatility_weights(snapshot, audit, target=0.10):
    names = sorted(audit.symbol.unique())
    returns = pd.concat(
        [
            snapshot.frames[n].close.pct_change(fill_method=None).rename(n)
            for n in names
        ],
        axis=1,
    )
    portfolio = returns.mean(axis=1, skipna=False)
    sigma = portfolio.rolling(20, min_periods=20).std() * np.sqrt(252)
    weights = (target / sigma.replace(0, np.nan)).clip(lower=0, upper=1)
    result = audit.feature_end.map(weights)
    if result.isna().any():
        raise ValueError("INSUFFICIENT_CAUSAL_VOLATILITY")
    return result.to_numpy(dtype=float)
