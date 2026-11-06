"""Small frozen target schemes, saved artifacts and exact score reconstruction."""

import copy
import time
import numpy as np
from equity_lab.data.sequence_daily import strict_json
from equity_lab.models.sequence.objectives import (
    target_transform,
    encode_targets,
    decode_scores,
)
from .artifacts import write_json
from .runner import model_config, _check


def score_saved(directory, raw_x):
    fit = strict_json(directory / "fit.json")
    with np.load(directory / "scaler.npz", allow_pickle=False) as scaler:
        x = ((raw_x - scaler["low"]) / scaler["span"]).astype(np.float32)
    transform = fit["transform"]
    if "constant" in fit:
        return np.full(len(x), fit["constant"])
    if fit["model"] == "linear":
        linear = strict_json(directory / "linear.json")
        raw = (
            x.reshape(len(x), -1) @ np.asarray(linear["coefficients"])
            + linear["intercept"]
        )
    else:
        import torch
        from equity_lab.models.sequence.checkpoint import load_checkpoint

        model, metadata = load_checkpoint(directory / "model.pt")
        if metadata["transform"] != transform:
            raise ValueError("CHECKPOINT_TARGET_MISMATCH")
        with torch.no_grad():
            raw = model(torch.tensor(x))["logits"].numpy()
    return decode_scores(raw, transform)


def fit_target(name, objective, samples, fold, seed, schedule, directory, deadline):
    if name not in ["prior", "linear", "matched", "equal", "sparse"]:
        raise ValueError("INVALID_TARGET_MODEL")
    _check(deadline)
    x = samples.x
    values = samples.audit[
        "target" if objective == "classification" else "forward_return"
    ].to_numpy()
    transform = target_transform(objective, values, fold.fit)
    low = x[fold.fit].min(axis=(0, 1))
    span = x[fold.fit].max(axis=(0, 1)) - low
    span[span == 0] = 1
    np.savez(directory / "scaler.npz", low=low, span=span)
    scaled = ((x - low) / span).astype(np.float32)
    target = encode_targets(values, transform).astype(np.float32)
    fit = dict(
        model=name,
        objective=objective,
        transform=transform,
        seed=seed,
        features=samples.features,
        history=[],
    )
    start = time.monotonic()
    if name == "prior" or (
        name == "linear"
        and objective == "classification"
        and len(set(values[fold.fit])) == 1
    ):
        fit["constant"] = transform["prior"]
    elif name == "linear":
        from sklearn.linear_model import LogisticRegression, Ridge
        from threadpoolctl import threadpool_limits

        model = (
            LogisticRegression(max_iter=500, random_state=seed)
            if objective == "classification"
            else Ridge(alpha=1.0, solver="svd")
        )
        with threadpool_limits(limits=2):
            model.fit(scaled[fold.fit].reshape(len(fold.fit), -1), target[fold.fit])
        write_json(
            directory / "linear.json",
            dict(
                coefficients=model.coef_.reshape(-1).tolist(),
                intercept=float(np.asarray(model.intercept_).reshape(-1)[0]),
            ),
        )
    else:
        import torch
        from equity_lab.models.sequence.checkpoint import build_model, save_checkpoint
        from equity_lab.models.sequence.objectives import task_loss

        torch.manual_seed(seed)
        torch.set_num_threads(2)
        torch.use_deterministic_algorithms(True)
        config = model_config(name, samples)
        model = build_model(config)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        xt = torch.tensor(scaled)
        yt = torch.tensor(target)
        best = None
        best_loss = float("inf")
        stale = 0
        processed = None
        for epoch in range(schedule["epochs"]):
            _check(deadline)
            model.train()
            losses = []
            order = torch.tensor(fold.fit)[torch.randperm(len(fold.fit))]
            for batch in order.split(schedule["batch_size"]):
                _check(deadline)
                out = model(xt[batch])
                loss = task_loss(out["logits"], yt[batch], objective)
                if not torch.isfinite(loss):
                    raise ValueError("NONFINITE_TASK_LOSS")
                total = loss + (0.01 if name == "sparse" else 0) * out["auxiliary"]
                optimizer.zero_grad()
                total.backward()
                optimizer.step()
                losses.append(float(loss.detach()))
                processed = [
                    a + b
                    for a, b in zip(
                        processed or [0] * len(out["processed"]), out["processed"]
                    )
                ]
            model.eval()
            with torch.no_grad():
                validation = float(
                    task_loss(
                        model(xt[fold.validation])["logits"],
                        yt[fold.validation],
                        objective,
                    )
                )
            if not np.isfinite(validation):
                raise ValueError("NONFINITE_VALIDATION_LOSS")
            fit["history"].append(
                dict(
                    epoch=epoch + 1,
                    task_loss=float(np.mean(losses)),
                    validation_loss=validation,
                )
            )
            if validation < best_loss:
                best_loss = validation
                best = copy.deepcopy(model.state_dict())
                stale = 0
                fit["best_epoch"] = epoch + 1
            else:
                stale += 1
            if stale >= schedule["patience"]:
                break
        model.load_state_dict(best)
        model.eval()
        save_checkpoint(
            model,
            directory / "model.pt",
            dict(transform=transform, features=samples.features, seed=seed),
        )
        with torch.no_grad():
            before = time.monotonic()
            out = model(xt[fold.test])
            elapsed = time.monotonic() - before
        np.savez_compressed(
            directory / "routing.npz",
            weights=out["weights"].numpy(),
            probabilities=out["probabilities"].numpy(),
        )
        fit.update(
            parameters=sum(p.numel() for p in model.parameters()),
            processed=out["processed"],
            training_processed=processed,
            inference_seconds=elapsed,
            config=config,
            mean_active_parameters=sum(p.numel() for p in model.parameters())
            - sum(
                sum(p.numel() for p in expert.parameters()) for expert in model.experts
            )
            + sum(
                count * sum(p.numel() for p in expert.parameters()) / len(fold.test)
                for count, expert in zip(out["processed"], model.experts)
            ),
            mean_gate_weights=out["weights"].mean(0).tolist(),
            processed_fraction=[count / len(fold.test) for count in out["processed"]],
        )
    fit["fit_seconds"] = time.monotonic() - start
    write_json(directory / "fit.json", fit)
    result = {
        part: score_saved(directory, x[indices])
        for part, indices in [("validation", fold.validation), ("test", fold.test)]
    }
    _check(deadline)
    if any(not np.isfinite(scores).all() for scores in result.values()):
        raise ValueError("NONFINITE_SCORES")
    return result
