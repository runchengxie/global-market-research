"""Fixed linear screen, reconstructible coefficients and cash-backed accounts."""

import csv
import math
import os
import time
from datetime import datetime, timezone
import numpy as np
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits
from .inputs import (
    PRODUCTS,
    INDICATORS,
    external,
    read,
    write,
    sha,
    seal,
    verify,
    load_prices,
    load_factors,
    instant,
)
from .features import ARMS, NAMES, samples, split_indices

FOLDS = [
    ("2026-04-01T00:00:00Z", "2026-06-01T00:00:00Z"),
    ("2026-06-01T00:00:00Z", "2026-08-01T00:00:00Z"),
    ("2026-08-01T00:00:00Z", "2026-10-01T00:00:00Z"),
]
FEES = [0, 10, 25]
BUDGET = {"fits": 36, "seconds": 600}


def fit_model(x, y, names):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if len(y) < 2 or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("INVALID_FIT_DATA")
    mean = x.mean(axis=0)
    scale = np.maximum(x.std(axis=0), 1e-8)
    ym = float(y.mean())
    ys = max(float(y.std()), 1e-8)
    with threadpool_limits(limits=1):
        model = Ridge(alpha=1.0).fit((x - mean) / scale, (y - ym) / ys)
    result = dict(
        schema="crypto.ridge_checkpoint.v1",
        features=names,
        x_mean=mean.tolist(),
        x_scale=scale.tolist(),
        y_mean=ym,
        y_scale=ys,
        coef=model.coef_.tolist(),
        intercept=float(model.intercept_),
    )
    if not np.allclose(
        predict_model(result, x),
        model.predict((x - mean) / scale) * ys + ym,
        atol=1e-12,
        rtol=0,
    ):
        raise ValueError("MODEL_RECONSTRUCTION")
    return result


def predict_model(model, x):
    return (
        ((np.asarray(x) - model["x_mean"]) / model["x_scale"]) @ np.array(model["coef"])
        + model["intercept"]
    ) * model["y_scale"] + model["y_mean"]


def cash_account(entry, exit, positions, fee_bps):
    if not (len(entry) == len(exit) == len(positions)) or not entry:
        raise ValueError("EMPTY_ACCOUNT")
    cash, shares, fee = 1.0, 0.0, fee_bps / 10000
    equity = []
    entry_marks = []
    exposure = []
    turnover = 0.0
    peak = 1.0
    drawdown = 0.0
    for opening, closing, position in zip(entry, exit, positions, strict=True):
        if position not in (0, 1) or min(opening, closing) <= 0:
            raise ValueError("INVALID_POSITION_OR_PRICE")
        before = cash + shares * opening
        if position and not shares:
            shares = cash / (opening * (1 + fee))
            cash = 0.0
            turnover += shares * opening / before
        elif not position and shares:
            turnover += shares * opening / before
            cash = shares * opening * (1 - fee)
            shares = 0.0
        entry_marks.append(cash + shares * opening)
        equity.append(cash + shares * closing)
        exposure.append(float(position))
        for value in [entry_marks[-1], equity[-1]]:
            peak = max(peak, value)
            drawdown = min(drawdown, value / peak - 1)
    if shares:
        cash = shares * exit[-1] * (1 - fee)
        shares = 0.0
        turnover += 1.0
        equity[-1] = cash
        drawdown = min(drawdown, cash / peak - 1)
    return dict(
        equity=equity,
        entry_equity=entry_marks,
        exposure=exposure,
        turnover=turnover,
        max_drawdown=drawdown,
    )


def freeze_screen(dataset, sentiment, expected_sha, output, source_revision):
    dataset = external(dataset)
    sentiment = external(sentiment)
    verify(dataset)
    if sha(sentiment) != expected_sha:
        raise ValueError("FACTOR_SOURCE_CHANGED")
    output = external(output)
    if any((p / "seal.json").exists() for p in output.parents):
        raise ValueError("OUTPUT_INSIDE_SEALED_EVIDENCE")
    if (
        output.is_relative_to(dataset)
        or dataset.is_relative_to(output)
        or sentiment.is_relative_to(output)
    ):
        raise ValueError("OUTPUT_OVERLAPS_INPUT")
    output.mkdir(parents=True, exist_ok=False)
    value = dict(
        schema="crypto.screen_plan.v1",
        frozen_at=datetime.now(timezone.utc).isoformat(),
        source_revision=source_revision,
        dataset=str(dataset),
        dataset_seal_sha256=sha(dataset / "seal.json"),
        sentiment=str(sentiment),
        sentiment_sha256=expected_sha,
        arms=ARMS,
        folds=FOLDS,
        fees=FEES,
        budget=BUDGET,
        expected_fits=24,
        claim_file=str(output.with_name(output.name + ".study-claim")),
        accepted_research=False,
    )
    write(output / "plan.json", value)
    return value


def rank_correlation(x, y):
    from scipy.stats import spearmanr

    if len(x) < 2 or np.std(x) == 0 or np.std(y) == 0:
        return None
    value = float(spearmanr(x, y).statistic)
    return value if math.isfinite(value) else None


def block_interval(fold_differences, step):
    rng = np.random.default_rng(147)
    draws = np.zeros(2000)
    total = sum(len(v) for v in fold_differences)
    block = 168 // step
    for values in fold_differences:
        chunks = [
            np.asarray(values[i : i + block]) for i in range(0, len(values), block)
        ]
        means = np.array([c.mean() for c in chunks])
        sizes = np.array([len(c) for c in chunks])
        indices = rng.integers(0, len(chunks), size=(2000, len(chunks)))
        draws += (
            (means[indices] * sizes[indices]).sum(axis=1)
            / sizes[indices].sum(axis=1)
            * len(values)
            / total
        )
    return [float(x) for x in np.quantile(draws, [0.025, 0.975])]


def run_screen(plan_file, output):
    plan_file = external(plan_file)
    plan = read(plan_file)
    plan_hash = sha(plan_file)
    if (
        plan["schema"] != "crypto.screen_plan.v1"
        or plan["arms"] != ARMS
        or plan["folds"] != [list(x) for x in FOLDS]
        or plan["fees"] != FEES
        or plan["budget"] != BUDGET
        or plan["expected_fits"] != 24
    ):
        raise ValueError("INVALID_SCREEN_PLAN")
    dataset = external(plan["dataset"])
    sentiment = external(plan["sentiment"])
    output = external(output)
    if any((p / "seal.json").exists() for p in output.parents):
        raise ValueError("OUTPUT_INSIDE_SEALED_EVIDENCE")
    if any(
        output.is_relative_to(p) or p.is_relative_to(output)
        for p in [dataset, plan_file.parent, sentiment]
    ):
        raise ValueError("OUTPUT_OVERLAPS_INPUT")
    if output.exists():
        raise FileExistsError("OUTPUT_EXISTS")
    claim = external(plan["claim_file"])
    if claim != plan_file.parent.with_name(plan_file.parent.name + ".study-claim"):
        raise ValueError("INVALID_STUDY_CLAIM")
    with claim.open("x") as f:
        os.chmod(claim, 0o600)
        f.write(plan_hash)
    output.mkdir(parents=True)
    (output / "models").mkdir()
    (output / "scores").mkdir()
    (output / "accounts").mkdir()
    write(output / "plan.json", plan)
    started = time.monotonic()
    ledger = dict(
        status="running", fits_started=0, fits_completed=0, completed_trials=0
    )
    write(output / "ledger.json", ledger)
    completed = []
    series = {}
    summaries = []
    try:
        if sha(dataset / "seal.json") != plan["dataset_seal_sha256"]:
            raise ValueError("DATASET_CHANGED")
        manifest, prices = load_prices(dataset)
        factors, factor_scope = load_factors(sentiment, plan["sentiment_sha256"])
        for step in [1, 4]:
            by_asset = {
                p: samples(prices[step][p], step, factors, INDICATORS) for p in PRODUCTS
            }
            for p, rows in by_asset.items():
                if not rows:
                    raise ValueError("NO_COMMON_SAMPLES")
                if [r["time"] for r in rows] != [
                    r["time"] for r in by_asset[PRODUCTS[0]]
                ]:
                    raise ValueError("UNPAIRED_ASSET_GRID")
            for fold, (start, end) in enumerate(FOLDS):
                pooled = [r for p in PRODUCTS for r in by_asset[p]]
                times = [r["time"] for r in pooled]
                train, test = split_indices(times, step, instant(start), instant(end))
                if len(train) < 100 or len(test) < 100:
                    raise ValueError("INSUFFICIENT_FOLD")
                y = np.array([r["target"] for r in pooled])
                prior = float(y[train].mean())
                predictions = {}
                models = {}
                for arm in ARMS:
                    if (
                        ledger["fits_started"] >= BUDGET["fits"]
                        or time.monotonic() - started >= BUDGET["seconds"]
                    ):
                        raise TimeoutError("STUDY_BUDGET")
                    ledger["fits_started"] += 1
                    write(output / "ledger.json", ledger)
                    x = np.array([r["features"][arm] for r in pooled])
                    names = NAMES + ([] if arm == "price_only" else INDICATORS)
                    model = fit_model(x[train], y[train], names)
                    model.update(
                        step_hours=step,
                        arm=arm,
                        fold=fold,
                        fit_last_exit=max(
                            pooled[i]["exit_time"] for i in train
                        ).isoformat(),
                        test_start=start,
                        source_revision=plan["source_revision"],
                    )
                    path = output / "models" / f"{step}h-{fold}-{arm}.json"
                    write(path, model)
                    score = predict_model(read(path), x[test])
                    predictions[arm] = score
                    models[arm] = model
                    if (
                        not np.isfinite(score).all()
                        or time.monotonic() - started >= BUDGET["seconds"]
                    ):
                        raise TimeoutError("STUDY_DEADLINE")
                    ledger["fits_completed"] += 1
                    write(output / "ledger.json", ledger)
                testing = [pooled[i] for i in test]
                predictions["prior"] = np.full(len(test), prior)
                prediction_rows = []
                for arm, score in predictions.items():
                    for r, s in zip(testing, score, strict=True):
                        prediction_rows.append(
                            dict(
                                asset=r["asset"],
                                decision_at=r["time"].isoformat(),
                                entry_at=r["entry_time"].isoformat(),
                                exit_at=r["exit_time"].isoformat(),
                                target=r["target"],
                                model=arm,
                                prediction=float(s),
                            )
                        )
                with (output / "scores" / f"{step}h-{fold}.csv").open(
                    "w", newline=""
                ) as f:
                    writer = csv.DictWriter(f, fieldnames=list(prediction_rows[0]))
                    writer.writeheader()
                    writer.writerows(prediction_rows)
                for arm in [*ARMS, "prior", "cash", "holding", "trend"]:
                    mse = (
                        float(np.mean((predictions[arm] - y[test]) ** 2))
                        if arm in predictions
                        else None
                    )
                    prior_mse = float(np.mean((prior - y[test]) ** 2))
                    skill = (
                        1 - mse / prior_mse
                        if mse is not None and prior_mse > 0
                        else None
                    )
                    correlations = []
                    for p in PRODUCTS:
                        idx = [i for i, r in enumerate(testing) if r["asset"] == p]
                        if arm in predictions:
                            correlations.append(
                                rank_correlation(predictions[arm][idx], y[test][idx])
                            )
                    ic = (
                        float(np.mean([v for v in correlations if v is not None]))
                        if any(v is not None for v in correlations)
                        else None
                    )
                    for fee in FEES:
                        accounts = {}
                        for p in PRODUCTS:
                            indices = [
                                i for i, r in enumerate(testing) if r["asset"] == p
                            ]
                            rows = [testing[i] for i in indices]
                            if arm in predictions:
                                positions = [
                                    int(predictions[arm][i] > 0.002) for i in indices
                                ]
                            elif arm == "holding":
                                positions = [1] * len(rows)
                            elif arm == "cash":
                                positions = [0] * len(rows)
                            else:
                                positions = [
                                    int(r["features"]["price_only"][2] > 0)
                                    for r in rows
                                ]
                            accounts[p] = cash_account(
                                [r["entry"] for r in rows],
                                [r["exit"] for r in rows],
                                positions,
                                fee,
                            )
                        equity = np.mean(
                            [a["equity"] for a in accounts.values()], axis=0
                        )
                        entries = np.mean(
                            [a["entry_equity"] for a in accounts.values()], axis=0
                        )
                        marks = np.column_stack([entries, equity]).ravel()
                        peaks = np.maximum.accumulate(np.r_[1.0, marks])
                        drawdown = float(np.min(np.r_[1.0, marks] / peaks - 1))
                        returns = np.diff(np.r_[1.0, equity]) / np.r_[1.0, equity][:-1]
                        row = dict(
                            step_hours=step,
                            fold=fold,
                            arm=arm,
                            fee_bps=fee,
                            bars=len(equity),
                            mse=mse,
                            skill=skill,
                            ic=ic,
                            net_return=float(equity[-1] - 1),
                            exposure=float(
                                np.mean(
                                    [np.mean(a["exposure"]) for a in accounts.values()]
                                )
                            ),
                            turnover=float(
                                np.mean([a["turnover"] for a in accounts.values()])
                            ),
                            max_drawdown=drawdown,
                        )
                        completed.append(row)
                        series[(step, fold, arm, fee)] = returns
                        write(
                            output / "accounts" / f"{step}h-{fold}-{arm}-{fee}.json",
                            dict(summary=row, assets=accounts),
                        )
                ledger["completed_trials"] += 1
                write(output / "ledger.json", ledger)
        for step in [1, 4]:
            for arm in [*ARMS, "prior", "cash", "holding", "trend"]:
                for fee in FEES:
                    rows = [
                        r
                        for r in completed
                        if r["step_hours"] == step
                        and r["arm"] == arm
                        and r["fee_bps"] == fee
                    ]
                    differences = [
                        series[(step, f, arm, fee)]
                        - series[(step, f, "price_only", fee)]
                        for f in range(3)
                    ]
                    summaries.append(
                        dict(
                            step_hours=step,
                            arm=arm,
                            fee_bps=fee,
                            folds=3,
                            net_return=float(
                                np.median([r["net_return"] for r in rows])
                            ),
                            skill=None
                            if rows[0]["skill"] is None
                            else float(np.mean([r["skill"] for r in rows])),
                            ic=None
                            if rows[0]["ic"] is None
                            else float(np.mean([r["ic"] for r in rows])),
                            exposure=float(np.mean([r["exposure"] for r in rows])),
                            turnover=float(np.mean([r["turnover"] for r in rows])),
                            max_drawdown=float(min(r["max_drawdown"] for r in rows)),
                            paired_mean=float(np.mean(np.concatenate(differences))),
                            paired_interval=block_interval(differences, step),
                        )
                    )
        verify(dataset)
        if sha(sentiment) != plan["sentiment_sha256"] or sha(plan_file) != plan_hash:
            raise ValueError("INPUT_CHANGED")
        ledger.update(status="completed", elapsed_seconds=time.monotonic() - started)
        if (
            ledger["fits_completed"] != 24
            or ledger["elapsed_seconds"] >= BUDGET["seconds"]
        ):
            raise TimeoutError("INCOMPLETE_STUDY")
    except (Exception, KeyboardInterrupt) as exc:
        ledger.update(
            status="partial",
            reason=type(exc).__name__ + ":" + str(exc),
            elapsed_seconds=time.monotonic() - started,
        )
    write(output / "ledger.json", ledger)
    result = dict(
        schema="crypto.factor_screen.v1",
        status=ledger["status"],
        source_revision=plan["source_revision"],
        plan_sha256=plan_hash,
        fit_count=ledger["fits_completed"],
        expected_fits=24,
        trial_count=len(completed),
        summary=summaries if ledger["status"] == "completed" else [],
        folds=completed,
        factor_scope=factor_scope if "factor_scope" in locals() else None,
        availability="historical_proxy_unverified",
        verified_factor_arm="blocked_missing_publication_and_revision_evidence",
        accepted_research=False,
        execution_authorized=False,
        elapsed_seconds=ledger["elapsed_seconds"],
    )
    write(output / "summary.json", result)
    seal(output)
    return result
