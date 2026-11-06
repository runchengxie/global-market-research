"""Audit sealed fitted checkpoints without refitting or changing source results."""

from pathlib import Path
import numpy as np
import pandas as pd
from .artifacts import (
    create_bundle,
    verify_bundle,
    seal_bundle,
    write_json,
    source_identity,
)
from .metrics import classification
from .account import replay_sequence
from .samples import build_samples, LEVEL_FEATURES


def audit_fitted_models(snapshot, run, output):
    import torch
    from equity_lab.data.sequence_daily import strict_json, digest
    from equity_lab.models.sequence.checkpoint import load_checkpoint

    torch.set_num_threads(2)
    run, output = Path(run), Path(output)
    verify_bundle(run)
    if output.resolve().is_relative_to(
        run.resolve()
    ) or output.resolve().is_relative_to(snapshot.root):
        raise ValueError("AUDIT_OUTPUT_MUST_BE_SEPARATE")
    source = strict_json(run / "config.json")
    if source["inputs"] != snapshot.bindings:
        raise ValueError("AUDIT_INPUT_MISMATCH")
    create_bundle(
        output,
        dict(
            schema="equity_lab.sequence_interventions.v1",
            source=source_identity(),
            parent_checksums_sha256=digest(run / "checksums.json"),
            accepted_research=False,
        ),
    )
    records = []
    cache = {}
    try:
        for checkpoint in sorted(run.glob("*/member-*/model.pt")):
            model, _ = load_checkpoint(checkpoint)
            if model.config["kind"] != "lstm" or model.config["experts"] != 3:
                continue
            directory = checkpoint.parent.parent
            task = strict_json(directory / "metrics.json")
            if task["model"] not in ["dense", "sparse", "top1", "shared_router"]:
                continue
            key = (model.config["lookback"], tuple(source["feature_order"]))
            if key not in cache:
                cache[key] = build_samples(
                    snapshot,
                    model.config["lookback"],
                    symbols=sorted(
                        pd.read_csv(run / "sample-audit.csv").symbol.unique()
                    ),
                    feature_mode="levels"
                    if source["feature_order"] == LEVEL_FEATURES
                    else "relative",
                )
            samples = cache[key]
            saved = pd.read_csv(directory / "predictions.csv")
            indices = strict_json(run / "folds.json")[task["fold"]]["test"]
            selected = strict_json(directory / "selected-features.json")["indices"]
            scaler = np.load(directory / "scaler.npz", allow_pickle=False)
            x = torch.tensor(
                (
                    (samples.x[indices][:, :, selected] - scaler["low"])
                    / scaler["span"]
                ).astype(np.float32)
            )
            with torch.no_grad():
                base = model(x)["logits"].sigmoid().numpy()
            if not np.allclose(base, saved.probability.to_numpy(), atol=1e-6):
                raise ValueError("CHECKPOINT_PREDICTION_MISMATCH")
            variants = (
                [("equal", "equal")]
                + [(f"drop-{i}", {"drop": i}) for i in range(3)]
                + [(f"only-{i}", {"only": i}) for i in range(3)]
            )
            for name, intervention in variants:
                with torch.no_grad():
                    out = model(x, intervention=intervention)
                    p = out["logits"].sigmoid().numpy()
                audit = saved.copy()
                audit["probability"] = p
                audit["prediction"] = (p > 0.5).astype(int)
                dest = output / f"{directory.name}-{name}"
                dest.mkdir()
                audit.to_csv(dest / "predictions.csv", index=False)
                accounts = {}
                for fee in [0, 5, 20, 40]:
                    account = replay_sequence(audit, fee)
                    write_json(dest / f"account-{fee}.json", account)
                    accounts[fee] = {
                        k: v for k, v in account.items() if k not in ["marks", "fills"]
                    }
                result = dict(
                    model=task["model"],
                    fold=task["fold"],
                    seed=task["seed"],
                    intervention=name,
                    processed=out["processed"],
                    classification=classification(audit.target, p),
                    accounts=accounts,
                    interpretation="Shared-head intervention on fixed weights; not independently trained expert predictors.",
                )
                write_json(dest / "metrics.json", result)
                records.append(result)
        snapshot.verify()
        verify_bundle(run)
        write_json(output / "summary.json", dict(status="completed", records=records))
    except BaseException:
        write_json(output / "summary.json", dict(status="invalid", records=records))
        raise
    finally:
        seal_bundle(output)
    return records
