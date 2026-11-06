"""Finite paired objective schemes on one causal sample and accounting contract."""

import json
import time
from pathlib import Path
import numpy as np
from .artifacts import source_identity, create_bundle, write_json, seal_bundle
from .runner import BudgetExpired, _check
from .target_fit import fit_target, score_saved
from .target_analysis import predictive_metrics
from .account import replay_allocations
from .controls import daily_returns, realized_volatility, causal_volatility_weights


GRIDS = {
    "classification": [0.35, 0.425, 0.5, 0.575, 0.65],
    "regression": [0.0, 0.0005, 0.001, 0.002, 0.004],
}
HURDLES = {"classification": 0.5, "regression": 0.001}


def freeze_target_schedule(folds, seeds=None, epochs=30, seconds=21600, max_fits=180):
    seeds = [11, 23, 37] if seeds is None else seeds
    if (
        type(folds) is not int
        or not 1 <= folds <= 7
        or not seeds
        or len(set(seeds)) != len(seeds)
        or any(type(s) is not int for s in seeds)
        or type(epochs) is not int
        or not 1 <= epochs <= 30
        or type(seconds) is not int
        or not 1 <= seconds <= 21600
        or type(max_fits) is not int
        or not 1 <= max_fits <= 180
    ):
        raise ValueError("INVALID_TARGET_SCHEDULE")
    tasks = []
    for fold in range(folds):
        tasks.extend(
            dict(fold=fold, model=m, objective="control", seed=0, fits=0)
            for m in ["cash", "holding", "volatility10"]
        )
        for objective in GRIDS:
            for model in ["prior", "linear", "matched", "equal", "sparse"]:
                for seed in [11] if model in ["prior", "linear"] else seeds:
                    tasks.append(
                        dict(
                            fold=fold,
                            model=model,
                            objective=objective,
                            seed=seed,
                            fits=int(model != "prior"),
                        )
                    )
    fits = sum(t["fits"] for t in tasks)
    if fits > max_fits:
        raise ValueError("FIT_BUDGET_EXCEEDED")
    return dict(
        schema="equity_lab.sequence_target_plan.v1",
        folds=folds,
        seeds=seeds,
        tasks=tasks,
        fits=fits,
        max_fits=max_fits,
        seconds=seconds,
        epochs=epochs,
        batch_size=128,
        patience=5,
        thresholds=GRIDS,
        hurdles=HURDLES,
    )


def select_target_threshold(validation, score, objective):
    grid = []
    for hurdle in GRIDS[objective]:
        rows = validation.copy()
        rows["allocation"] = (score > hurdle).astype(float)
        account = replay_allocations(rows, 5)
        grid.append(
            dict(
                threshold=hurdle,
                mean_daily_net_return=float(daily_returns(account).mean()),
                trades=account["trades"],
            )
        )
    best = max(
        grid,
        key=lambda r: (
            r["mean_daily_net_return"],
            -abs(r["threshold"] - HURDLES[objective]),
            r["threshold"],
        ),
    )
    return best["threshold"], grid


def _account(rows, weights, fee):
    rows = rows.copy()
    rows["allocation"] = weights
    result = replay_allocations(rows, fee)
    result.update(
        realized_annual_volatility=realized_volatility(result),
        realized_mean_open_exposure=float(
            np.mean([m["open_exposure"] for m in result["marks"]])
        ),
        daily_returns=daily_returns(result).tolist(),
    )
    return result


def run_target_study(schedule, snapshot, samples, folds, output):
    expected = freeze_target_schedule(
        schedule["folds"],
        seeds=schedule["seeds"],
        epochs=schedule["epochs"],
        seconds=schedule["seconds"],
        max_fits=schedule["max_fits"],
    )
    if schedule != expected:
        raise ValueError("INVALID_TARGET_SCHEDULE")
    deadline = time.monotonic() + schedule["seconds"]
    output = Path(output)
    resolved = output.resolve()
    if resolved.is_relative_to(snapshot.root) or any(
        (p / ".git").exists() for p in [resolved, *resolved.parents]
    ):
        raise ValueError("OUTPUT_MUST_BE_EXTERNAL")
    if len(folds) != schedule["folds"]:
        raise ValueError("FOLD_SCHEDULE_MISMATCH")
    original_bindings = json.loads(json.dumps(snapshot.bindings))
    snapshot.verify()
    config = dict(
        schema="equity_lab.sequence_target_study.v1",
        schedule=schedule,
        inputs=original_bindings,
        source=source_identity(),
        features=samples.features,
        accepted_research=False,
        execution_authorized=False,
        scope="Retrospective fixed-current, split-adjusted price units, no dividends; full target/loss/policy comparison",
        continuation_rule="Design frozen before fitting; Brier/rawMSE lower95>0, net5bps lower95>0 vs three models/exposure,fee20mean>0 and5of7folds per model; expansion still blocked without independent forward evidence",
    )
    create_bundle(output, config)
    samples.audit.to_csv(output / "sample-audit.csv", index=False)
    write_json(
        output / "folds.json",
        [
            dict(
                fold=i,
                fit=f.fit.tolist(),
                validation=f.validation.tolist(),
                test=f.test.tolist(),
                fit_cutoff=f.fit_cutoff,
                selection_cutoff=f.selection_cutoff,
                ready_ts=f.ready_ts,
            )
            for i, f in enumerate(folds)
        ],
    )
    summary = dict(
        schema=config["schema"],
        status="running",
        schedule=schedule,
        completed=[],
        pending=list(schedule["tasks"]),
        fits_completed=0,
        fits_started=0,
        reason=None,
    )
    try:
        for index, task in enumerate(schedule["tasks"]):
            _check(deadline)
            fold = folds[task["fold"]]
            val = samples.audit.iloc[fold.validation].copy()
            test = samples.audit.iloc[fold.test].copy()
            test["signal_ts"] = test.available_ts.clip(lower=fold.ready_ts)
            if (
                not (test.signal_ts < test.entry_ts).all()
                or val.label_available_ts.max() >= test.entry_ts.min()
            ):
                raise ValueError("NONCAUSAL_TARGET_SELECTION")
            directory = output / f"{index:04d}-{task['objective']}-{task['model']}"
            directory.mkdir()
            record = dict(
                **task,
                dates=sorted(test.exit_session.unique()),
                accounts={},
                metrics={},
                loss_daily=[],
                rank_ic_daily=[],
            )
            if task["objective"] == "control":
                allocations = {
                    "fixed": np.full(len(test), float(task["model"] == "holding"))
                    if task["model"] != "volatility10"
                    else causal_volatility_weights(snapshot, test)
                }
            else:
                summary["fits_started"] += task["fits"]
                scores = fit_target(
                    task["model"],
                    task["objective"],
                    samples,
                    fold,
                    task["seed"],
                    schedule,
                    directory,
                    deadline,
                )
                if not np.allclose(
                    scores["test"],
                    score_saved(directory, samples.x[fold.test]),
                    atol=1e-8,
                    rtol=0,
                ):
                    raise ValueError("SAVED_SCORE_MISMATCH")
                objective = task["objective"]
                score = scores["test"]
                vscore = scores["validation"]
                threshold, grid = select_target_threshold(val, vscore, objective)
                validation_exposure = float((vscore > HURDLES[objective]).mean())
                allocations = dict(
                    fixed=(score > HURDLES[objective]).astype(float),
                    validation=(score > threshold).astype(float),
                    exposure=np.full(len(test), validation_exposure),
                )
                fit = json.loads((directory / "fit.json").read_text())
                metrics, losses, ics = predictive_metrics(
                    test, objective, score, fit["transform"]["prior"]
                )
                record.update(
                    metrics=metrics,
                    loss_daily=losses,
                    rank_ic_daily=ics,
                    selected_threshold=threshold,
                    threshold_candidates=grid,
                    validation_exposure=validation_exposure,
                    selection_cutoff=str(fold.selection_cutoff),
                    model_ready_ts=str(fold.ready_ts),
                    fit=fit,
                )
                for name, rows, values in [
                    ("validation", val, vscore),
                    ("test", test, score),
                ]:
                    rows = rows.copy()
                    rows["score"] = values
                    rows["score_kind"] = (
                        "probability"
                        if objective == "classification"
                        else "expected_return"
                    )
                    rows["target_value"] = (
                        rows.target
                        if objective == "classification"
                        else rows.forward_return
                    )
                    rows.to_csv(directory / (name + "-scores.csv"), index=False)
            for policy, weights in allocations.items():
                record["accounts"][policy] = {}
                for fee in [0, 5, 20, 40]:
                    _check(deadline)
                    account = _account(test, weights, fee)
                    _check(deadline)
                    fixed = record["accounts"].get("fixed", {}).get(str(fee))
                    for metric, label in [
                        ("exposure", "target_exposure_gap_to_fixed"),
                        (
                            "realized_mean_open_exposure",
                            "realized_exposure_gap_to_fixed",
                        ),
                        (
                            "realized_annual_volatility",
                            "realized_volatility_gap_to_fixed",
                        ),
                    ]:
                        account[label] = (
                            account[metric] - fixed[metric] if fixed else 0.0
                        )
                    write_json(directory / f"account-{policy}-{fee}.json", account)
                    record["accounts"][policy][str(fee)] = {
                        k: v for k, v in account.items() if k not in ["marks", "fills"]
                    }
            _check(deadline)
            summary["completed"].append(record)
            summary["pending"] = schedule["tasks"][index + 1 :]
            summary["fits_completed"] += task["fits"]
            write_json(directory / "record.json", record)
            write_json(output / "summary.json", summary)
            print(
                json.dumps(
                    dict(
                        completed=len(summary["completed"]),
                        total=len(schedule["tasks"]),
                        fits=summary["fits_completed"],
                        model=task["model"],
                        objective=task["objective"],
                        fold=task["fold"],
                        seed=task["seed"],
                    )
                ),
                flush=True,
            )
        _check(deadline)
        summary["status"] = "completed"
    except KeyboardInterrupt:
        summary.update(status="partial", reason="INTERRUPTED")
    except BudgetExpired:
        summary.update(status="partial", reason="WALL_CLOCK_BUDGET")
    except Exception as exc:
        summary.update(status="invalid", reason=type(exc).__name__)
        raise
    finally:
        try:
            snapshot.verify()
            if snapshot.bindings != original_bindings:
                raise ValueError("INPUT_BINDING_CHANGED")
        except (ValueError, OSError):
            summary.update(status="invalid", reason="INPUT_CHANGED")
        write_json(output / "summary.json", summary)
        seal_bundle(output)
    return summary
