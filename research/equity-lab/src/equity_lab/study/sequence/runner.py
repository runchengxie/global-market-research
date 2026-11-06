"""Bounded offline fits and complete, private out-of-sample audit bundles."""

import copy
import importlib.metadata
import json
import platform
import subprocess
import time
from pathlib import Path
import numpy as np
from .artifacts import create_bundle, seal_bundle, write_json
from .account import replay_sequence
from .metrics import classification, paired_report


class BudgetExpired(RuntimeError):
    pass


def _check(deadline):
    if time.monotonic() >= deadline:
        raise BudgetExpired("WALL_CLOCK_BUDGET")


def model_config(name, samples):
    from equity_lab.models.sequence.lstm import parameter_matched_width

    config = dict(
        kind="lstm",
        features=samples.x.shape[-1],
        lookback=samples.x.shape[1],
        units=64,
        experts=3,
    )
    if name in ["lstm64", "ensemble", "matched"]:
        config["experts"] = 1
    if name == "matched":
        config["units"] = parameter_matched_width(dict(config, experts=3))
    if name == "equal":
        config["equal"] = True
    if name in ["sparse", "top1", "shared_router", "drop_expert"]:
        config["top_k"] = 1 if name == "top1" else 2
    if name == "shared_router":
        config["shared_router"] = True
    if name == "drop_expert":
        config.update(experts=2, top_k=None)
    if name.startswith("transformer"):
        config = dict(
            kind="transformer",
            features=samples.x.shape[-1],
            lookback=samples.x.shape[1],
            top_k=2 if name.endswith("sparse") else None,
            width=64,
        )
    return config


def _fit_neural(name, samples, x, fold, seed, schedule, directory, deadline):
    import torch
    from equity_lab.models.sequence.checkpoint import build_model, save_checkpoint

    torch.manual_seed(seed)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    config = model_config(name, samples)
    model = build_model(config)
    optimizer = torch.optim.Adam(model.parameters())
    y = torch.tensor(samples.audit.target.to_numpy(), dtype=torch.float32)
    xt = torch.tensor(x)
    best, best_loss, stale, history = None, float("inf"), 0, []
    started = time.monotonic()
    for epoch in range(schedule["epochs"]):
        _check(deadline)
        model.train()
        total, aux, batches = 0.0, 0.0, 0
        order = torch.tensor(fold.fit)[torch.randperm(len(fold.fit))]
        for batch in order.split(schedule["batch_size"]):
            _check(deadline)
            out = model(xt[batch])
            task_loss = torch.nn.functional.binary_cross_entropy_with_logits(
                out["logits"], y[batch]
            )
            coefficient = 0.01 if config.get("top_k") is not None else 0.0
            loss = task_loss + coefficient * out["auxiliary"]
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total += float(task_loss.detach())
            aux += float(out["auxiliary"].detach())
            batches += 1
        model.eval()
        with torch.no_grad():
            vo = model(xt[fold.validation])
            validation = float(
                torch.nn.functional.binary_cross_entropy_with_logits(
                    vo["logits"], y[fold.validation]
                )
            )
        history.append(
            dict(
                epoch=epoch + 1,
                task_loss=total / batches,
                auxiliary_loss=aux / batches,
                validation_loss=validation,
            )
        )
        if validation < best_loss:
            best_loss, stale = validation, 0
            best = copy.deepcopy(model.state_dict())
        else:
            stale += 1
        if stale >= schedule["patience"]:
            break
    model.load_state_dict(best)
    model.eval()
    fit_seconds = time.monotonic() - started
    with torch.no_grad():
        warm = model(xt[fold.test])
        timings = []
        for _ in range(5):
            before = time.monotonic()
            out = model(xt[fold.test])
            timings.append(time.monotonic() - before)
    save_checkpoint(
        model, directory / "model.pt", dict(seed=seed, feature_order=samples.features)
    )
    np.savez_compressed(
        directory / "routing.npz",
        probabilities=out["probabilities"].numpy(),
        weights=out["weights"].numpy(),
        expert_probes=out["probes"].numpy(),
    )
    write_json(
        directory / "training.json",
        dict(
            history=history,
            config=config,
            fit_seconds=fit_seconds,
            inference_seconds=timings,
            warmup_calls=1,
            parameters=sum(p.numel() for p in model.parameters()),
            processed=warm["processed"],
            thread_count=2,
            deterministic=True,
        ),
    )
    return out["logits"].sigmoid().numpy()


def fit_prediction(name, samples, fold, seed, schedule, directory, deadline):
    a = samples.audit
    x = samples.x
    # Pooled fit-window statistics; no validation/test row enters scaling.
    low = x[fold.fit].min(axis=(0, 1))
    span = x[fold.fit].max(axis=(0, 1)) - low
    span[span == 0] = 1
    scaled = ((x - low) / span).astype(np.float32)
    np.savez(
        directory / "scaler.npz",
        low=low,
        span=span,
        features=np.asarray(samples.features),
    )
    if name in ["cash", "holding", "momentum"]:
        if name == "momentum":
            # Frozen relative moving-average deviation, known at the signal close.
            return (
                x[fold.test, -1, samples.features.index("ma20_deviation")] > 0
            ).astype(float)
        return np.full(len(fold.test), float(name == "holding"))
    if name == "logistic":
        from sklearn.linear_model import LogisticRegression

        y = a.iloc[fold.fit].target.to_numpy()
        if len(set(y)) < 2:
            write_json(
                directory / "linear.json",
                dict(constant=float(y[0]), reason="one_fit_class"),
            )
            return np.full(len(fold.test), float(y[0]))
        from threadpoolctl import threadpool_limits

        with threadpool_limits(limits=2):
            model = LogisticRegression(random_state=seed, max_iter=500).fit(
                scaled[fold.fit].reshape(len(fold.fit), -1), y
            )
        write_json(
            directory / "linear.json",
            dict(
                coefficients=model.coef_.tolist(),
                intercept=model.intercept_.tolist(),
                classes=model.classes_.tolist(),
            ),
        )
        return model.predict_proba(scaled[fold.test].reshape(len(fold.test), -1))[:, 1]
    members = []
    for member in range(3 if name == "ensemble" else 1):
        _check(deadline)
        dest = directory / f"member-{member}"
        dest.mkdir()
        members.append(
            _fit_neural(
                name,
                samples,
                scaled,
                fold,
                seed + member * 1000,
                schedule,
                dest,
                deadline,
            )
        )
    return np.mean(members, axis=0)


def run_study(schedule, snapshot, samples, folds, output):
    output = Path(output)
    if output.resolve().is_relative_to(
        snapshot.root
    ) or output.resolve().is_relative_to(Path(__file__).resolve().parents[6]):
        raise ValueError("OUTPUT_MUST_BE_EXTERNAL")
    config = dict(
        schema="equity_lab.sequence_study.v1",
        schedule=schedule,
        feature_order=samples.features,
        accepted_research=False,
        synthetic_price_units=True,
        dividends=False,
        source_revision=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        limitations=[
            "fixed_current",
            "previously_exposed",
            "availability_unverified",
            "publication_rights_unverified",
        ],
        inputs=snapshot.bindings,
        python=platform.python_version(),
        platform=platform.platform(),
        packages={
            d.metadata["Name"]: d.version for d in importlib.metadata.distributions()
        },
    )
    create_bundle(output, config)
    samples.audit.to_csv(output / "sample-audit.csv", index=False)
    fold_records = [
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
    ]
    write_json(output / "folds.json", fold_records)
    deadline = time.monotonic() + schedule["seconds"]
    summary = dict(
        status="running", completed=[], pending=list(schedule["tasks"]), reason=None
    )
    paired = []
    try:
        snapshot.verify()
        for index, task in enumerate(schedule["tasks"]):
            _check(deadline)
            directory = output / f"{index:04d}-{task['model']}"
            directory.mkdir()
            fold = folds[task["fold"]]
            probabilities = fit_prediction(
                task["model"],
                samples,
                fold,
                task["seed"],
                schedule,
                directory,
                deadline,
            )
            audit = samples.audit.iloc[fold.test].copy()
            audit["probability"] = probabilities
            audit["prediction"] = (probabilities > 0.5).astype(int)
            audit["model_ready_ts"] = fold.ready_ts
            audit.to_csv(directory / "predictions.csv", index=False)
            scores = classification(audit.target, probabilities)
            accounts = {}
            for fee in [0, 5, 20, 40]:
                account = replay_sequence(audit, fee)
                write_json(directory / f"account-{fee}.json", account)
                accounts[fee] = {
                    k: v for k, v in account.items() if k not in ["marks", "fills"]
                }
            for row in audit.itertuples():
                paired.append(
                    dict(
                        fold=task["fold"],
                        seed=task["seed"],
                        date=row.feature_end,
                        model=task["model"],
                        value=-float((row.target - row.probability) ** 2),
                    )
                )
            result = dict(
                **task,
                classification=scores,
                accounts=accounts,
                zero_trade=accounts[5]["trades"] == 0,
            )
            summary["completed"].append(result)
            summary["pending"] = schedule["tasks"][index + 1 :]
            write_json(directory / "metrics.json", result)
            write_json(output / "summary.json", summary)
            print(
                json.dumps(
                    dict(
                        completed=index + 1,
                        total=len(schedule["tasks"]),
                        model=task["model"],
                        fold=task["fold"],
                        seed=task["seed"],
                    )
                ),
                flush=True,
            )
        summary["status"] = "completed"
    except BudgetExpired as exc:
        summary.update(status="partial", reason=str(exc))
    except Exception as exc:
        summary.update(status="invalid", reason=type(exc).__name__)
        raise
    finally:
        try:
            snapshot.verify()
        except ValueError:
            summary.update(status="invalid", reason="INPUT_CHANGED")
        write_json(output / "summary.json", summary)
        write_json(
            output / "paired-brier.json",
            paired_report(paired, reference="matched") if paired else {},
        )
        seal_bundle(output)
    return summary
