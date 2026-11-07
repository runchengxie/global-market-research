"""Explain existing prediction distributions without fitting or selecting rules."""

import csv
import numpy as np
from ..intraday.inputs import verify, read, sha

HURDLES = [0, 0.001, 0.002]
QUANTILES = [0, 0.01, 0.1, 0.5, 0.9, 0.99, 1]


def distribution(predictions, targets):
    p, y = np.asarray(predictions, float), np.asarray(targets, float)
    if (
        len(p) == 0
        or p.shape != y.shape
        or not np.isfinite(p).all()
        or not np.isfinite(y).all()
    ):
        raise ValueError("INVALID_DISTRIBUTION")
    return dict(
        count=len(p),
        prediction_quantiles=np.quantile(p, QUANTILES).tolist(),
        target_quantiles=np.quantile(y, QUANTILES).tolist(),
        above_hurdles=[float(np.mean(p > h)) for h in HURDLES],
    )


def diagnose_scores(study):
    verify(study)
    result = []
    for path in sorted((study / "scores").glob("*.csv")):
        with path.open() as f:
            rows = list(csv.DictReader(f))
        step, fold = path.stem.split("-")
        for model in sorted({r["model"] for r in rows}):
            selected = [r for r in rows if r["model"] == model]
            result.append(
                dict(
                    step_hours=int(step[:-1]),
                    fold=int(fold),
                    model=model,
                    **distribution(
                        [float(r["prediction"]) for r in selected],
                        [float(r["target"]) for r in selected],
                    ),
                )
            )
    return dict(
        schema="crypto.cash_diagnostics.v1",
        study_seal=sha(study / "seal.json"),
        status=read(study / "summary.json")["status"],
        quantile_levels=QUANTILES,
        hurdles=HURDLES,
        rows=result,
        scope="retrospective_explanation_no_rule_selection",
    )
