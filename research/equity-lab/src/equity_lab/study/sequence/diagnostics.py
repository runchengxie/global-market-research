"""Retrospective frozen-model diagnostics; no neural refit or test-set selection."""

import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
from equity_lab.data.sequence_daily import digest, strict_json
from .artifacts import (
    create_bundle,
    write_json,
    seal_bundle,
    verify_bundle,
    source_identity,
)
from .samples import build_samples, LEVEL_FEATURES
from .controls import (
    score_diagnostics,
    choose_threshold,
    validation_controls,
    causal_volatility_weights,
    realized_volatility,
)
from .account import replay_allocations

FAMILIES = {"matched", "equal", "dense", "sparse"}


def _scores(directory, samples, indices):
    """Read the actual fitted artifact; arrays retain original feature order."""
    selected = strict_json(directory / "selected-features.json")["indices"]
    scaler = np.load(directory / "scaler.npz", allow_pickle=False)
    x = ((samples.x[indices][:, :, selected] - scaler["low"]) / scaler["span"]).astype(
        np.float32
    )
    task = strict_json(directory / "metrics.json")
    name = task["model"]
    if name in ["cash", "holding"]:
        return np.full(len(indices), float(name == "holding"))
    if name == "momentum":
        return (
            samples.x[indices, -1, samples.features.index("ma20_deviation")] > 0
        ).astype(float)
    if name == "logistic":
        linear = strict_json(directory / "linear.json")
        if "constant" in linear:
            return np.full(len(indices), linear["constant"])
        if linear["classes"] != [0, 1]:
            raise ValueError("INVALID_LINEAR_CLASSES")
        z = (
            x.reshape(len(indices), -1) @ np.asarray(linear["coefficients"])[0]
            + linear["intercept"][0]
        )
        return np.exp(-np.logaddexp(0, -z))
    import torch
    from equity_lab.models.sequence.checkpoint import load_checkpoint

    torch.set_num_threads(2)
    scores = []
    checkpoints = sorted(directory.glob("member-*/model.pt"))
    if len(checkpoints) != (3 if name == "ensemble" else 1):
        raise ValueError("MISSING_CHECKPOINT")
    for checkpoint in checkpoints:
        model, _ = load_checkpoint(checkpoint)
        with torch.no_grad():
            scores.append(model(torch.tensor(x))["logits"].sigmoid().numpy())
    return np.mean(scores, axis=0)


def _router(directory):
    result = []
    for file in sorted(directory.glob("member-*/routing.npz")):
        with np.load(file, allow_pickle=False) as data:
            weights = data["weights"]
            probabilities = data["probabilities"]
            normalized = weights / weights.sum(1, keepdims=True).clip(1e-12)
            entropy = -(normalized * np.log(normalized.clip(1e-12))).sum(1)
            config = strict_json(file.parent / "training.json")["config"]
            active = (
                (config.get("top_k") is not None)
                if config["kind"] == "transformer"
                else config.get("experts", 1) > 1 and not config.get("equal", False)
            )
            result.append(
                dict(
                    member=file.parent.name,
                    gating_active=active,
                    scope="pooled_tokens_and_layers"
                    if config["kind"] == "transformer"
                    else "window",
                    mean_weight_mass=float(weights.sum(1).mean()),
                    mean_weights=weights.mean(0).tolist(),
                    processed_fraction=(weights > 0).mean(0).tolist(),
                    mean_router_probabilities=probabilities.mean(0).tolist(),
                    mean_weight_entropy=float(entropy.mean()),
                )
            )
    return result


def _clock_frame(samples, indices, fold, probability):
    rows = samples.audit.iloc[indices].copy()
    rows["probability"] = probability
    rows["model_ready_ts"] = pd.Timestamp(fold["ready_ts"])
    return rows


def diagnose_run(snapshot, parent, output, seconds=1800):
    if type(seconds) is not int or not 1 <= seconds <= 1800:
        raise ValueError("INVALID_DIAGNOSTIC_BUDGET")
    parent, output = Path(parent), Path(output)
    if output.resolve().is_relative_to(
        parent.resolve()
    ) or output.resolve().is_relative_to(snapshot.root):
        raise ValueError("OUTPUT_MUST_BE_SEPARATE")
    if any(
        (p / ".git").exists() for p in [output.resolve(), *output.resolve().parents]
    ):
        raise ValueError("OUTPUT_MUST_BE_EXTERNAL")
    verify_bundle(parent)
    source = strict_json(parent / "config.json")
    summary = strict_json(parent / "summary.json")
    if summary["status"] != "completed" or source["inputs"] != snapshot.bindings:
        raise ValueError("PARENT_NOT_COMPLETE_OR_INPUT_MISMATCH")
    snapshot.verify()
    folds = strict_json(parent / "folds.json")
    # The old bundle's feature count/order and sample audit are the source contract.
    audit = pd.read_csv(parent / "sample-audit.csv")
    checkpoint = next(parent.glob("*/member-*/model.pt"), None)
    if checkpoint is None:
        raise ValueError("MISSING_CHECKPOINT")
    from equity_lab.models.sequence.checkpoint import load_checkpoint

    first, _ = load_checkpoint(checkpoint)
    samples = build_samples(
        snapshot,
        first.config["lookback"],
        symbols=sorted(audit.symbol.unique()),
        feature_mode="levels"
        if source["feature_order"] == LEVEL_FEATURES
        else "relative",
    )
    if samples.features != source["feature_order"] or samples.audit[
        ["symbol", "feature_end"]
    ].to_dict("list") != audit[["symbol", "feature_end"]].to_dict("list"):
        raise ValueError("SAMPLE_IDENTITY_MISMATCH")
    create_bundle(
        output,
        dict(
            schema="equity_lab.sequence_diagnostics.v1",
            source=source_identity(),
            parent_checksums_sha256=digest(parent / "checksums.json"),
            accepted_research=False,
            seconds=seconds,
            costs=[0, 5, 20, 40],
            threshold_selection="validation mean net daily return at5bps",
            caveats=[
                "retrospective_exposed_history",
                "validation_also_used_for_early_stopping",
                "risk_targets_are_validation_frozen_not_exact_test_matches",
            ],
        ),
    )
    (output / "accounts").mkdir()
    records = []
    deadline = time.monotonic() + seconds
    result = dict(
        schema="equity_lab.sequence_diagnostics.v1",
        provenance=dict(
            parent_checksums_sha256=digest(parent / "checksums.json"),
            data_manifest_sha256=snapshot.bindings["manifest.json"]["sha256"],
            code_revision=source_identity()["revision"],
        ),
        status="running",
        records=records,
        pending=len(summary["completed"]),
        reason=None,
    )
    try:
        for index, task in enumerate(summary["completed"]):
            if time.monotonic() >= deadline:
                result.update(status="partial", reason="WALL_CLOCK_BUDGET")
                break
            directory = parent / f"{index:04d}-{task['model']}"
            saved = pd.read_csv(directory / "predictions.csv")
            fold = folds[task["fold"]]
            test_p = _scores(directory, samples, fold["test"])
            if not np.allclose(test_p, saved.probability.to_numpy(), atol=1e-6, rtol=0):
                raise ValueError("CHECKPOINT_PREDICTION_MISMATCH")
            if not np.array_equal(
                saved.target.to_numpy(),
                samples.audit.iloc[fold["test"]].target.to_numpy(),
            ):
                raise ValueError("TEST_TARGET_MISMATCH")
            val_p = _scores(directory, samples, fold["validation"])
            val = _clock_frame(samples, fold["validation"], fold, val_p)
            test = _clock_frame(samples, fold["test"], fold, test_p)
            test["signal_ts"] = test.available_ts.clip(
                lower=pd.Timestamp(fold["ready_ts"])
            )
            if (
                not (test.signal_ts < test.entry_ts).all()
                or val.label_available_ts.max() >= test.entry_ts.min()
            ):
                raise ValueError("DIAGNOSTIC_SELECTION_NOT_AVAILABLE")
            record = dict(
                model=task["model"],
                fold=task["fold"],
                seed=task["seed"],
                source_task=directory.name,
                fit_base_rate=float(samples.audit.iloc[fold["fit"]].target.mean()),
                validation=score_diagnostics(val.target, val_p),
                test=score_diagnostics(test.target, test_p),
                router=_router(directory),
                selection_source="validation_only",
                gate_used=False,
                selection_cutoff=str(fold["selection_cutoff"]),
                model_ready_ts=str(fold["ready_ts"]),
                accounts={},
                threshold_candidates=[],
            )
            record["gate_used"] = any(r["gating_active"] for r in record["router"])
            prior = record["fit_base_rate"]
            prior_brier = float(np.mean((test.target.to_numpy() - prior) ** 2))
            record["test"]["fit_prior_brier"] = prior_brier
            record["test"]["brier_skill_vs_fit_prior"] = (
                1 - record["test"]["brier"] / prior_brier if prior_brier > 0 else None
            )
            record["test"]["flat_reason"] = (
                "all_scores_at_or_below_cutoff"
                if record["test"]["above_cutoff"] == 0
                else None
            )
            record["dates"] = sorted(test.exit_session.unique())
            allocations = {"original": (test_p > 0.5).astype(float)}
            if task["model"] in FAMILIES:
                threshold, grid = choose_threshold(val)
                control = validation_controls(val)
                record.update(
                    selected_threshold=threshold,
                    threshold_candidates=grid,
                    validation_targets=control,
                )
                allocations = {
                    "original": (test_p > 0.5).astype(float),
                    "constant_25": np.full(len(test), 0.25),
                    "constant_50": np.full(len(test), 0.5),
                    "validation_exposure": np.full(len(test), control["exposure"]),
                    "validation_volatility": np.full(len(test), control["volatility"]),
                    "causal_volatility_10": causal_volatility_weights(snapshot, test),
                    "validation_threshold": (test_p > threshold).astype(float),
                }
            for name, weights in allocations.items():
                rows = test.copy()
                rows["allocation"] = weights
                record["accounts"][name] = {}
                for fee in [0, 5, 20, 40]:
                    account = replay_allocations(rows, fee)
                    account["realized_annual_volatility"] = realized_volatility(account)
                    account["exposure_gap_to_model"] = float(
                        weights.mean() - (test_p > 0.5).mean()
                    )
                    write_json(
                        output / "accounts" / f"{index:04d}-{name}-{fee}.json",
                        account,
                    )
                    compact = {
                        k: v for k, v in account.items() if k not in ["marks", "fills"]
                    }
                    compact["equity"] = [m["equity"] for m in account["marks"]]
                    compact["open_exposure"] = [
                        m["open_exposure"] for m in account["marks"]
                    ]
                    record["accounts"][name][str(fee)] = compact
                    if name == "original":
                        old = strict_json(directory / f"account-{fee}.json")
                        if any(
                            not np.isclose(account[k], old[k], atol=1e-10, rtol=0)
                            for k in ["return", "drawdown", "cost", "turnover"]
                        ):
                            raise ValueError("BINARY_ACCOUNT_PARITY_FAILED")
            records.append(record)
            result["pending"] = len(summary["completed"]) - len(records)
            if len(records) % 10 == 0:
                write_json(output / "summary.json", result)
            print(
                json.dumps(
                    dict(diagnostic=len(records), total=len(summary["completed"]))
                ),
                flush=True,
            )
        else:
            result["status"] = "completed"
    except KeyboardInterrupt:
        result.update(status="partial", reason="INTERRUPTED")
    except Exception as exc:
        result.update(status="invalid", reason=type(exc).__name__)
        raise
    finally:
        try:
            snapshot.verify()
            verify_bundle(parent)
        except ValueError:
            result.update(status="invalid", reason="INPUT_CHANGED")
        write_json(output / "summary.json", result)
        from .viewer import write_viewer

        write_viewer(result, output / "browser.html")
        seal_bundle(output)
    return result
