"""Exploratory diagnostics; no evidence promotion or cross-fold NAV stitching."""

import numpy as np
import pandas as pd


def classification(y, probabilities):
    from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss

    p = np.asarray(probabilities, dtype=float)
    y = np.asarray(y)
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("INVALID_PROBABILITIES")
    bins = []
    for i in range(10):
        mask = (p >= i / 10) & ((p < (i + 1) / 10) if i < 9 else (p <= 1))
        bins.append(
            dict(
                bin=i,
                count=int(mask.sum()),
                predicted=float(p[mask].mean()) if mask.any() else None,
                observed=float(y[mask].mean()) if mask.any() else None,
            )
        )
    return dict(
        auc=float(roc_auc_score(y, p)) if len(set(y)) == 2 else None,
        auc_reason=None if len(set(y)) == 2 else "one_class",
        log_loss=float(log_loss(y, p, labels=[0, 1])),
        brier=float(brier_score_loss(y, p)),
        reliability=bins,
        accuracy=float(((p > 0.5) == y).mean()),
    )


def paired_report(results, reference, block_length=20, draws=2000, seed=20261106):
    frame = pd.DataFrame(results)
    # Aggregate same-date stocks before resampling; fold/seed remain distinct groups.
    keys = ["fold", "date"] + (["seed"] if "seed" in frame else [])
    wide = frame.groupby([*keys, "model"]).value.mean().unstack("model")
    if reference not in wide:
        return {}
    rng = np.random.default_rng(seed)
    report = {}
    for model in wide.columns:
        if model == reference:
            continue
        paired = wide[[reference, model]].dropna()
        segments = [
            g[model].to_numpy() - g[reference].to_numpy()
            for _, g in paired.groupby(level=[k for k in keys if k != "date"])
        ]
        if not segments or min(map(len, segments)) < block_length:
            report[model] = dict(
                difference=None, interval=None, reason="insufficient_paired_dates"
            )
            continue
        samples = []
        for _ in range(draws):
            resampled = []
            for segment in segments:
                starts = rng.integers(
                    0,
                    len(segment) - block_length + 1,
                    size=int(np.ceil(len(segment) / block_length)),
                )
                resampled.extend(
                    np.concatenate([segment[s : s + block_length] for s in starts])[
                        : len(segment)
                    ]
                )
            samples.append(float(np.mean(resampled)))
        report[model] = dict(
            difference=float(np.concatenate(segments).mean()),
            interval=np.quantile(samples, [0.025, 0.975]).tolist(),
            reason=None,
        )
    return report
