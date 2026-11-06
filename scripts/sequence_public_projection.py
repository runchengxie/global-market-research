"""Publish only explicitly selected aggregate sequence-study fields, never raw series."""

import argparse
import hashlib
import json
from pathlib import Path


def verified(path, name):
    path = Path(path)
    inventory = json.loads((path / "checksums.json").read_text())
    entries = list(path.rglob("*"))
    actual = {
        str(p.relative_to(path))
        for p in entries
        if p.is_file() and p.name != "checksums.json"
    }
    if any(p.is_symlink() for p in entries) or actual != set(inventory):
        raise ValueError("INVALID_PUBLICATION_SOURCE")
    for relative, expected in inventory.items():
        file = Path(relative)
        if (
            file.is_absolute()
            or ".." in file.parts
            or (path / file).is_symlink()
            or hashlib.sha256((path / file).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("INVALID_PUBLICATION_SOURCE")
    if name not in inventory:
        raise ValueError("UNBOUND_PUBLICATION_SOURCE")
    return json.loads((path / name).read_text())


def project(primary, diagnostics, target=None, target_run=None):
    config = verified(primary, "config.json")
    old = verified(diagnostics, "summary.json")
    if old["status"] != "completed" or old["records"] != 350:
        raise ValueError("INCOMPLETE_DIAGNOSTIC_SOURCE")

    manifest_sha = "b1807afa61024cfca79b07e3a858748060abfe4ad36325c3bd7669c7fedccef8"
    if (
        config.get("inputs", {}).get("manifest.json", {}).get("sha256") != manifest_sha
        or old.get("source", {}).get("data_manifest_sha256") != manifest_sha
    ):
        raise ValueError("PUBLICATION_SCOPE_MISMATCH")

    def training(name):
        file = next(Path(primary).glob("*-" + name + "/member-0/training.json"))
        return json.loads(file.read_text())

    dense = training("dense")
    matched = training("matched")
    rows = []
    for name in ["matched", "equal", "dense", "sparse"]:
        m = old["models"][name]
        a = m["controls"]
        p = m["paired_daily_difference_vs_original_fee5"]["validation_threshold"]
        rows.append(
            dict(
                model=name,
                cases=m["cases"],
                flat=m["zero_score_above_cutoff"],
                auc=m["mean_auc"],
                brier_skill=m["mean_brier_skill_vs_fit_prior"],
                net_return=a["original"]["5"]["median_fold_seed_mean_return"],
                threshold_return=a["validation_threshold"]["5"][
                    "median_fold_seed_mean_return"
                ],
                exposure=a["original"]["5"]["mean_realized_open_exposure"],
                threshold_exposure=a["validation_threshold"]["5"][
                    "mean_realized_open_exposure"
                ],
                daily_difference=p["difference"],
                daily_interval=p["interval"],
            )
        )
    control = old["models"]
    result = dict(
        schema="sequence_research_public.v1",
        scope="retrospective_aggregate_only",
        accepted_research=False,
        execution_authorized=False,
        sample=dict(
            stocks=10,
            sessions=953,
            start="2023-01-03",
            end="2026-10-20",
            currency="USD",
            price_basis="split_adjusted",
            dividends=False,
            fixed_current=True,
            previously_exposed=True,
        ),
        architecture=dict(
            lookback=dense["config"]["lookback"],
            features=dense["config"]["features"],
            experts=dense["config"]["experts"],
            units=dense["config"]["units"],
            top_k=2,
            representation=dense["config"]["lookback"] * dense["config"]["units"],
            parameters=dense["parameters"],
            matched_units=matched["config"]["units"],
            matched_parameters=matched["parameters"],
            router_context="last_feature_row",
            mix="hidden_representation",
        ),
        primary=dict(
            folds=7,
            seeds=5,
            cases=350,
            fee_bps=5,
            rows=rows,
            holding_return=control["holding"]["controls"]["original"]["5"][
                "median_fold_seed_mean_return"
            ],
            volatility_return=control["matched"]["controls"]["causal_volatility_10"][
                "5"
            ]["median_fold_seed_mean_return"],
        ),
        target=dict(
            status="pending",
            folds=7,
            seeds=3,
            cases=0,
            fits=0,
            epochs=30,
            batch_size=128,
            rows=[],
            continuation=[],
        ),
        explorations=[
            dict(id="primary", status="completed", cases=350, fits=315),
            dict(id="checkpoint", status="completed", cases=490, fits=0),
            dict(id="diagnostics", status="completed", cases=350, fits=0),
            dict(id="targets", status="pending", cases=0, fits=0),
            dict(id="transformer", status="planned", cases=0, fits=0),
            dict(id="crypto", status="planned", cases=0, fits=0),
        ],
        source_revisions=dict(
            primary=config["source_revision"]["revision"],
            diagnostics=old["source"]["code_revision"],
            target=None,
        ),
    )
    if target is not None:
        report = verified(target, "analysis.json")
        summary = verified(target_run, "summary.json")
        tc = verified(target_run, "config.json")
        ac = verified(target, "config.json")
        if (
            ac["parent_checksums_sha256"]
            != hashlib.sha256(
                (Path(target_run) / "checksums.json").read_bytes()
            ).hexdigest()
            or report["status"] != "completed"
            or summary["status"] != "completed"
            or len(summary["completed"]) != 175
            or summary["fits_completed"] != 140
        ):
            raise ValueError("INCOMPLETE_TARGET_SOURCE")
        if tc["inputs"] != config["inputs"] or any(
            summary["schedule"][key] != value
            for key, value in dict(
                folds=7, seeds=[11, 23, 37], epochs=30, batch_size=128, patience=5
            ).items()
        ):
            raise ValueError("PUBLICATION_SCOPE_MISMATCH")
        result["target"].update(status="completed", cases=175, fits=140)
        for objective, data in report["objectives"].items():
            for name, m in data["models"].items():
                a = m["accounts"]
                result["target"]["rows"].append(
                    dict(
                        objective=objective,
                        model=name,
                        cases=m["cases"],
                        skill=m["mean_prediction_skill"],
                        ic=m["mean_daily_rank_ic"],
                        net_return=a["fixed_5"]["median_fold_seed_mean_return"],
                        threshold_return=a["validation_5"][
                            "median_fold_seed_mean_return"
                        ],
                        exposure=a["fixed_5"]["mean_realized_exposure"],
                        threshold_exposure=a["validation_5"]["mean_realized_exposure"],
                        volatility=a["fixed_5"]["mean_realized_volatility"],
                    )
                )
            checks = data["continuation"]["checks"]
            result["target"]["continuation"].append(
                dict(
                    objective=objective,
                    status=data["continuation"]["status"],
                    passed_checks=sum(checks.values()),
                    total_checks=len(checks),
                )
            )
        result["explorations"][3].update(status="completed", cases=175, fits=140)
        result["source_revisions"]["target"] = tc["source"]["revision"]
    return result


def main():
    p = argparse.ArgumentParser(__doc__)
    for name in ["primary", "diagnostics", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--target", type=Path)
    p.add_argument("--target-run", type=Path)
    a = p.parse_args()
    out = a.output.resolve()
    if any((n / ".git").exists() for n in [out, *out.parents]):
        raise ValueError("GENERATE_EXTERNALLY_BEFORE_REVIEWED_PUBLICATION")
    if any(
        out.is_relative_to(Path(source).resolve())
        for source in [a.primary, a.diagnostics, a.target, a.target_run]
        if source is not None
    ):
        raise ValueError("PUBLICATION_OUTPUT_MUST_BE_SEPARATE")
    if (a.target is None) != (a.target_run is None):
        raise ValueError("TARGET_AND_RUN_REQUIRED_TOGETHER")
    result = project(a.primary, a.diagnostics, a.target, a.target_run)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write("\n")
    print("Aggregate-only publication projection generated")


if __name__ == "__main__":
    main()
