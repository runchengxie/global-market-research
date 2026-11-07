"""Plan-bound retrospective sequence comparison with validation-only decisions."""

import csv
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
from ..intraday.inputs import (
    external,
    verify,
    read,
    write,
    sha,
    seal,
    load_prices,
    load_factors,
    INDICATORS,
    instant,
)
from ..intraday.features import samples
from ..intraday.study import FOLDS, FEES, cash_account, fit_model, predict_model

SEEDS = [11, 29, 47]
CONFIG = dict(
    step_hours=4,
    lookback=12,
    features=7,
    units=8,
    seeds=SEEDS,
    epochs=5,
    batch_size=256,
    learning_rate=0.001,
    validation_days=30,
    hurdles=[0, 0.001, 0.002],
    fees=FEES,
    kinds=["ridge", "single", "matched", "equal", "dense"],
    expected_fits=39,
    budget=dict(fits=45, seconds=900),
)


def make_windows(rows, lookback=12):
    windows, out = [], []
    for asset in sorted({r["asset"] for r in rows}):
        group = sorted(
            [r for r in rows if r["asset"] == asset], key=lambda r: r["time"]
        )
        if any(
            b["time"] - a["time"] != timedelta(hours=4)
            for a, b in zip(group, group[1:])
        ):
            raise ValueError("WINDOW_GRID_GAP")
        for i in range(lookback - 1, len(group)):
            windows.append(
                [r["features"]["price_only"] for r in group[i - lookback + 1 : i + 1]]
            )
            out.append(group[i])
    if not out:
        raise ValueError("EMPTY_WINDOWS")
    order = sorted(range(len(out)), key=lambda i: (out[i]["time"], out[i]["asset"]))
    return np.asarray(windows, float)[order], [out[i] for i in order]


def split_sample(rows, start, end, validation_days=30):
    boundary = start - timedelta(days=validation_days)
    fit = np.array([i for i, r in enumerate(rows) if r["exit_time"] < boundary], int)
    val = np.array(
        [
            i
            for i, r in enumerate(rows)
            if boundary <= r["time"] and r["exit_time"] < start
        ],
        int,
    )
    test = np.array([i for i, r in enumerate(rows) if start <= r["time"] < end], int)
    if not all(len(v) > 1 for v in [fit, val, test]):
        raise ValueError("INSUFFICIENT_SPLIT")
    return fit, val, test


def account(rows, score, hurdle, fee):
    assets = {}
    for asset in sorted({r["asset"] for r in rows}):
        idx = [i for i, r in enumerate(rows) if r["asset"] == asset]
        group = [rows[i] for i in idx]
        assets[asset] = cash_account(
            [r["entry"] for r in group],
            [r["exit"] for r in group],
            [int(score[i] > hurdle) for i in idx],
            fee,
        )
    curves = [a["equity"] for a in assets.values()]
    if len({len(x) for x in curves}) != 1:
        raise ValueError("UNPAIRED_ACCOUNT_GRID")
    equity = np.mean(curves, axis=0)
    entries = np.mean([a["entry_equity"] for a in assets.values()], axis=0)
    marks = np.r_[1.0, np.column_stack([entries, equity]).ravel()]
    return dict(
        net_return=float(equity[-1] - 1),
        exposure=float(np.mean([np.mean(a["exposure"]) for a in assets.values()])),
        turnover=float(np.mean([a["turnover"] for a in assets.values()])),
        max_drawdown=float(np.min(marks / np.maximum.accumulate(marks) - 1)),
    ), dict(assets=assets, equity=equity.tolist())


def select_hurdle(score, rows):
    return max(
        CONFIG["hurdles"],
        key=lambda h: (account(rows, score, h, 10)[0]["net_return"], h),
    )


def new_output(path, inputs):
    path = external(Path(path))
    if any((p / "seal.json").exists() for p in path.parents) or any(
        path.is_relative_to(p) or p.is_relative_to(path) for p in inputs
    ):
        raise ValueError("OUTPUT_OVERLAPS_INPUT")
    path.mkdir(parents=True, exist_ok=False)
    return path


def freeze_comparison(dataset, study, output, source_revision):
    dataset, study = external(dataset), external(study)
    verify(dataset)
    verify(study)
    original = read(study / "plan.json")
    if len(source_revision) != 40 or any(
        c not in "0123456789abcdef" for c in source_revision
    ):
        raise ValueError("SOURCE_REVISION_REQUIRED")
    out = new_output(output, [dataset, study])
    plan = dict(
        schema="crypto.comparison_plan.v1",
        frozen_at=datetime.now(timezone.utc).isoformat(),
        source_revision=source_revision,
        dataset=str(dataset),
        study=str(study),
        dataset_seal=sha(dataset / "seal.json"),
        study_seal=sha(study / "seal.json"),
        factor_source=original["sentiment"],
        factor_sha256=original["sentiment_sha256"],
        config=CONFIG,
        folds=FOLDS,
        claim=str(out.with_name(out.name + ".claim")),
        scope="retrospective_exploration_not_fresh_holdout",
    )
    write(out / "plan.json", plan)
    seal(out)
    return plan


def claim_plan(plan_file):
    plan_file = external(plan_file)
    verify(plan_file.parent)
    plan = read(plan_file)
    if (
        plan["config"] != CONFIG
        or plan["folds"] != [list(x) for x in FOLDS]
        or plan["schema"] != "crypto.comparison_plan.v1"
    ):
        raise ValueError("PLAN_CONFIG_CHANGED")
    claim = external(Path(plan["claim"]))
    if claim != plan_file.parent.with_name(plan_file.parent.name + ".claim"):
        raise ValueError("INVALID_CLAIM")
    with claim.open("x") as f:
        os.chmod(claim, 0o600)
        f.write(sha(plan_file))
    return plan


def run_comparison(plan_file, output):
    import torch
    from .models import Model

    plan = claim_plan(plan_file)
    dataset, study = Path(plan["dataset"]), Path(plan["study"])
    out = new_output(
        output, [dataset, study, Path(plan_file).parent, Path(plan["factor_source"])]
    )
    for sub in ["checkpoints", "scores", "accounts"]:
        (out / sub).mkdir()
    write(out / "plan.json", plan)
    ledger = dict(status="running", fits_started=0, fits_completed=0, elapsed_seconds=0)
    write(out / "ledger.json", ledger)
    started = time.monotonic()
    results = []
    architecture = {}
    gate_rows = []
    torch.set_num_threads(1)

    def budget(start=False):
        ledger["elapsed_seconds"] = time.monotonic() - started
        if ledger["elapsed_seconds"] >= CONFIG["budget"]["seconds"] or (
            start and ledger["fits_started"] >= CONFIG["budget"]["fits"]
        ):
            raise TimeoutError("COMPARISON_BUDGET")
        if start:
            ledger["fits_started"] += 1
        write(out / "ledger.json", ledger)

    try:
        verify(study)
        if (
            sha(dataset / "seal.json") != plan["dataset_seal"]
            or sha(study / "seal.json") != plan["study_seal"]
        ):
            raise ValueError("INPUT_CHANGED")
        _, prices = load_prices(dataset)
        factors, _ = load_factors(Path(plan["factor_source"]), plan["factor_sha256"])
        rows = [
            r
            for asset in prices[4]
            for r in samples(prices[4][asset], 4, factors, INDICATORS)
        ]
        x, rows = make_windows(rows)
        y = np.array([r["target"] for r in rows])
        for fold, (a, b) in enumerate(FOLDS):
            fit, val, test = split_sample(rows, instant(a), instant(b))
            valrows = [rows[i] for i in val]
            testrows = [rows[i] for i in test]
            mean = x[fit].mean(axis=(0, 1))
            scale = np.maximum(x[fit].std(axis=(0, 1)), 1e-8)
            ym = float(y[fit].mean())
            ys = max(float(y[fit].std()), 1e-8)
            scaled = ((x - mean) / scale).astype("float32")
            target = ((y - ym) / ys).astype("float32")
            for kind in CONFIG["kinds"]:
                for seed in [0] if kind == "ridge" else SEEDS:
                    budget(True)
                    name = f"{fold}-{kind}-{seed}"
                    if kind == "ridge":
                        model = fit_model(
                            x[fit].reshape(len(fit), -1),
                            y[fit],
                            [f"{i}:{j}" for i in range(12) for j in range(7)],
                        )
                        write(out / "checkpoints" / f"{name}.json", model)
                        pred = predict_model(model, x.reshape(len(x), -1))
                        parameters = 85
                        gates = None
                    else:
                        torch.manual_seed(seed)
                        np.random.seed(seed)
                        model = Model(kind)
                        parameters = sum(p.numel() for p in model.parameters())
                        opt = torch.optim.Adam(model.parameters(), lr=0.001)
                        xx = torch.from_numpy(scaled)
                        yy = torch.from_numpy(target)
                        for epoch in range(5):
                            order = torch.randperm(len(fit)).numpy()
                            for offset in range(0, len(fit), 256):
                                budget()
                                idx = fit[order[offset : offset + 256]]
                                opt.zero_grad()
                                predicted, _ = model(xx[idx])
                                loss = ((predicted - yy[idx]) ** 2).mean()
                                if not torch.isfinite(loss):
                                    raise ValueError("NONFINITE_FIT")
                                loss.backward()
                                opt.step()
                        model.eval()
                        weights = {
                            k: v.detach().numpy() for k, v in model.state_dict().items()
                        }
                        np.savez_compressed(
                            out / "checkpoints" / f"{name}.npz", **weights
                        )
                        reconstructed = Model(kind)
                        with np.load(
                            out / "checkpoints" / f"{name}.npz", allow_pickle=False
                        ) as w:
                            reconstructed.load_state_dict(
                                {k: torch.from_numpy(w[k].copy()) for k in w.files}
                            )
                        with torch.no_grad():
                            outputs = [
                                reconstructed(xx[i : i + 512])
                                for i in range(0, len(xx), 512)
                            ]
                            pred = torch.cat([v[0] for v in outputs]).numpy() * ys + ym
                            gates = torch.cat([v[1] for v in outputs]).numpy()
                            if not torch.allclose(
                                model(xx[test[:8]])[0],
                                reconstructed(xx[test[:8]])[0],
                                atol=1e-7,
                            ):
                                raise ValueError("CHECKPOINT_RECONSTRUCTION")
                        write(
                            out / "checkpoints" / f"{name}.json",
                            dict(
                                kind=kind,
                                seed=seed,
                                x_mean=mean.tolist(),
                                x_scale=scale.tolist(),
                                y_mean=ym,
                                y_scale=ys,
                                parameters=parameters,
                            ),
                        )
                    if not np.isfinite(pred).all():
                        raise ValueError("NONFINITE_PREDICTION")
                    architecture[kind] = parameters
                    chosen = select_hurdle(pred[val], valrows)
                    ledger["fits_completed"] += 1
                    budget()
                    if gates is not None:
                        g = gates[test]
                        gate_rows.append(
                            dict(
                                fold=fold,
                                kind=kind,
                                seed=seed,
                                mean_weights=g.mean(0).tolist(),
                                entropy=float(
                                    -(g * np.log(np.maximum(g, 1e-12))).sum(1).mean()
                                ),
                            )
                        )
                    with (out / "scores" / f"{name}.csv").open("w", newline="") as f:
                        writer = csv.DictWriter(
                            f,
                            fieldnames=[
                                "split",
                                "asset",
                                "decision_at",
                                "entry_at",
                                "exit_at",
                                "target",
                                "prediction",
                            ],
                        )
                        writer.writeheader()
                        for split, idx in [("validation", val), ("test", test)]:
                            for i in idx:
                                r = rows[i]
                                writer.writerow(
                                    dict(
                                        split=split,
                                        asset=r["asset"],
                                        decision_at=r["time"].isoformat(),
                                        entry_at=r["entry_time"].isoformat(),
                                        exit_at=r["exit_time"].isoformat(),
                                        target=r["target"],
                                        prediction=float(pred[i]),
                                    )
                                )
                    mse = float(np.mean((pred[test] - y[test]) ** 2))
                    prior = float(np.mean((ym - y[test]) ** 2))
                    for rule, hurdle in [("fixed", 0.002), ("validation", chosen)]:
                        for fee in FEES:
                            metrics, accounts = account(
                                testrows, pred[test], hurdle, fee
                            )
                            row = dict(
                                fold=fold,
                                kind=kind,
                                seed=seed,
                                rule=rule,
                                hurdle=hurdle,
                                fee_bps=fee,
                                mse=mse,
                                skill=1 - mse / prior if prior > 0 else None,
                                parameters=parameters,
                                fit_samples=len(fit),
                                validation_samples=len(val),
                                test_samples=len(test),
                                **metrics,
                            )
                            results.append(row)
                            write(
                                out / "accounts" / f"{name}-{rule}-{fee}.json",
                                dict(summary=row, **accounts),
                            )
        budget()
        if ledger["fits_completed"] != 39:
            raise ValueError("INCOMPLETE_COMPARISON")
        ledger["status"] = "completed"
    except (Exception, KeyboardInterrupt) as exc:
        ledger.update(status="partial", reason=type(exc).__name__ + ":" + str(exc))
    finally:
        ledger["elapsed_seconds"] = time.monotonic() - started
        write(out / "ledger.json", ledger)
        result = dict(
            schema="crypto.comparison_result.v1",
            source_revision=plan["source_revision"],
            scope=plan["scope"],
            plan_sha256=sha(plan_file),
            **ledger,
            architecture=architecture,
            rows=results,
            gates=gate_rows,
            accepted_research=False,
            execution_authorized=False,
        )
        write(out / "summary.json", result)
        seal(out)
    return result
