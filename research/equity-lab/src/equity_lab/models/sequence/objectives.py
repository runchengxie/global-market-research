"""Fit-only target transforms; network outputs stay in their declared units."""

import numpy as np


def target_transform(objective, values, fit):
    values = np.asarray(values, dtype=float)
    if (
        objective not in ["classification", "regression"]
        or not np.isfinite(values).all()
        or not len(fit)
    ):
        raise ValueError("INVALID_TARGET")
    if objective == "classification":
        if not np.isin(values, [0, 1]).all():
            raise ValueError("INVALID_BINARY_TARGET")
        return dict(
            objective=objective, center=0.0, scale=1.0, prior=float(values[fit].mean())
        )
    return dict(
        objective=objective,
        center=float(values[fit].mean()),
        scale=max(float(values[fit].std()), 1e-6),
        prior=float(values[fit].mean()),
    )


def encode_targets(values, transform):
    return (np.asarray(values) - transform["center"]) / transform["scale"]


def decode_scores(raw, transform):
    raw = np.asarray(raw, dtype=float)
    return (
        np.exp(-np.logaddexp(0, -raw))
        if transform["objective"] == "classification"
        else raw * transform["scale"] + transform["center"]
    )


def task_loss(raw, encoded, objective):
    import torch

    if objective == "classification":
        return torch.nn.functional.binary_cross_entropy_with_logits(raw, encoded)
    if objective == "regression":
        return torch.nn.functional.mse_loss(raw, encoded)
    raise ValueError("INVALID_OBJECTIVE")
