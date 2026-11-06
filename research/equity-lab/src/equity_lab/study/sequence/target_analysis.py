"""Proper per-target scores and predeclared retrospective continuation checks."""

import numpy as np
import pandas as pd
from .controls import score_diagnostics
from .metrics import paired_report


def predictive_metrics(rows, objective, score, prior):
    y = (
        rows.target.to_numpy()
        if objective == "classification"
        else rows.forward_return.to_numpy()
    )
    loss = (y - score) ** 2
    reference = (y - prior) ** 2
    daily = []
    ics = []
    frame = rows.copy()
    frame["loss"] = loss
    frame["score"] = score
    for day, g in frame.groupby("exit_session", sort=True):
        daily.append(dict(date=day, value=-float(g.loss.mean())))
        if len(g) > 1 and g.score.nunique() > 1 and g.forward_return.nunique() > 1:
            ics.append(
                dict(
                    date=day, value=float(g.score.rank().corr(g.forward_return.rank()))
                )
            )
    baseline = float(reference.mean())
    metrics = dict(
        brier=None,
        auc=None,
        mse=float(loss.mean()) if objective == "regression" else None,
        mae=float(np.abs(y - score).mean()) if objective == "regression" else None,
        prediction_skill=1 - float(loss.mean()) / baseline if baseline > 0 else None,
        prior_loss=baseline,
        mean_daily_rank_ic=float(np.mean([r["value"] for r in ics])) if ics else None,
        rank_ic_days=len(ics),
        rank_ic_missing_days=rows.exit_session.nunique() - len(ics),
    )
    if objective == "classification":
        metrics.update(score_diagnostics(y, score))
    return metrics, daily, ics


def continuation_rule(contrasts, folds, expected_folds=7):
    keys = ["linear", "matched", "equal", "exposure", "prior"]
    if len(set(folds)) != expected_folds or not set(keys) <= set(contrasts):
        return dict(status="insufficient_evidence", expand_moe=False, checks={})
    checks = {}
    for name in keys:
        c = contrasts[name]
        interval = c.get("interval")
        checks[name + "_positive_lower95"] = interval is not None and interval[0] > 0
        if name in ["linear", "matched", "equal"]:
            checks[name + "_positive_fee20"] = (
                c.get("fee20_difference") is not None and c["fee20_difference"] > 0
            )
            checks[name + "_positive_folds"] = c.get("positive_folds", 0) >= 5
    return dict(
        status="promising_retrospective"
        if all(checks.values())
        else "continue_deferred",
        expand_moe=False,
        checks=checks,
        reason="Independent accepted forward evidence required even if retrospective checks pass",
    )


def _expanded(records, objective, seeds, fee=None, loss=False):
    result = []
    for r in records:
        if r["objective"] not in [objective, "control"]:
            continue
        if loss:
            if r["objective"] == "control":
                continue
            entries = {"loss": r["loss_daily"]}
        else:
            entries = {
                policy: [
                    dict(date=day, value=value)
                    for day, value in zip(
                        r["dates"], account[str(fee)]["daily_returns"]
                    )
                ]
                for policy, account in r["accounts"].items()
            }
        for policy, values in entries.items():
            for seed in (
                seeds
                if r["model"] in ["prior", "linear", "cash", "holding", "volatility10"]
                else [r["seed"]]
            ):
                for row in values:
                    result.append(
                        dict(
                            fold=r["fold"],
                            seed=seed,
                            date=row["date"],
                            model=r["model"] if loss else r["model"] + "." + policy,
                            value=row["value"],
                        )
                    )
    return result


def analyze_targets(summary, draws=2000):
    results = {}
    schedule = summary["schedule"]
    records = summary["completed"]
    for objective in ["classification", "regression"]:
        selected = [r for r in records if r["objective"] == objective]
        by_fee = {}
        raw = {}
        for fee in [5, 20]:
            rows = _expanded(records, objective, schedule["seeds"], fee=fee)
            raw[fee] = pd.DataFrame(rows)
            # Sparse minus each reference: paired_report reports model-reference.
            by_fee[fee] = {}
            for reference in [
                "linear.fixed",
                "matched.fixed",
                "equal.fixed",
                "sparse.exposure",
            ]:
                by_fee[fee][reference] = (
                    paired_report(
                        [r for r in rows if r["model"] in [reference, "sparse.fixed"]],
                        reference,
                        draws=draws,
                    ).get("sparse.fixed")
                    if rows
                    else None
                )
        losses = _expanded(records, objective, schedule["seeds"], loss=True)
        prior_comparison = (
            paired_report(
                [r for r in losses if r["model"] in ["prior", "sparse"]],
                "prior",
                draws=draws,
            ).get("sparse")
            if losses
            else None
        )
        contrasts = {}
        for name, reference in [
            ("linear", "linear.fixed"),
            ("matched", "matched.fixed"),
            ("equal", "equal.fixed"),
            ("exposure", "sparse.exposure"),
        ]:
            primary = by_fee[5][reference]
            if primary is None:
                continue
            positive = 0
            if not raw[5].empty:
                wide = (
                    raw[5]
                    .groupby(["fold", "date", "model"])
                    .value.mean()
                    .unstack("model")
                )
                if {"sparse.fixed", reference} <= set(wide):
                    positive = int(
                        (
                            (wide["sparse.fixed"] - wide[reference])
                            .groupby("fold")
                            .mean()
                            > 0
                        ).sum()
                    )
            contrasts[name] = dict(
                **primary,
                fee20_difference=(by_fee[20][reference] or {}).get("difference"),
                positive_folds=positive,
            )
        if prior_comparison is not None:
            contrasts["prior"] = prior_comparison
        expected = {
            (fold, model, seed)
            for fold in range(schedule["folds"])
            for model in ["prior", "linear", "matched", "equal", "sparse"]
            for seed in ([11] if model in ["prior", "linear"] else schedule["seeds"])
        }
        actual = {(r["fold"], r["model"], r["seed"]) for r in selected}
        complete = summary["status"] == "completed" and actual == expected
        gate = continuation_rule(
            contrasts, list(range(schedule["folds"])) if complete else [], 7
        )
        model_metrics = {}
        for name in ["prior", "linear", "matched", "equal", "sparse"]:
            rows = [r for r in selected if r["model"] == name]
            if not rows:
                continue
            model_metrics[name] = dict(
                cases=len(rows),
                mean_prediction_skill=float(
                    np.mean(
                        [
                            r["metrics"]["prediction_skill"]
                            for r in rows
                            if r["metrics"]["prediction_skill"] is not None
                        ]
                    )
                )
                if any(r["metrics"]["prediction_skill"] is not None for r in rows)
                else None,
                mean_daily_rank_ic=float(
                    np.mean(
                        [
                            r["metrics"]["mean_daily_rank_ic"]
                            for r in rows
                            if r["metrics"]["mean_daily_rank_ic"] is not None
                        ]
                    )
                )
                if any(r["metrics"]["mean_daily_rank_ic"] is not None for r in rows)
                else None,
                accounts={},
            )
            for policy in ["fixed", "validation", "exposure"]:
                for fee in ["0", "5", "20", "40"]:
                    frame = pd.DataFrame(
                        [
                            dict(
                                fold=r["fold"],
                                **{
                                    k: v
                                    for k, v in r["accounts"][policy][fee].items()
                                    if k not in ["daily_returns"]
                                },
                            )
                            for r in rows
                        ]
                    )
                    model_metrics[name]["accounts"][policy + "_" + fee] = dict(
                        median_fold_seed_mean_return=float(
                            frame.groupby("fold")["return"].mean().median()
                        ),
                        mean_realized_exposure=float(
                            frame.realized_mean_open_exposure.mean()
                        ),
                        mean_realized_volatility=float(
                            frame.realized_annual_volatility.mean()
                        ),
                        zero_trade_cases=int((frame.trades == 0).sum()),
                    )
        results[objective] = dict(
            complete=complete,
            continuation=gate,
            contrasts=contrasts,
            models=model_metrics,
        )
    return dict(
        schema="equity_lab.sequence_target_analysis.v1",
        status=summary["status"],
        accepted_research=False,
        execution_authorized=False,
        expand_moe=False,
        block_length=20,
        draws=draws,
        seed_averaging="Same market date before resampling; deterministic controls broadcast without refitting",
        caveats=[
            "previously_exposed_history",
            "validation_reused_for_early_stopping",
            "complete_target_loss_policy_schemes_not_label_only_effect",
            "unadjusted_exploratory_intervals",
            "no_stitched_fold_nav",
        ],
        objectives=results,
    )
