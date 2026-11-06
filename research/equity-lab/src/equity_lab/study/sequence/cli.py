"""Offline sequence study: plan, run and verify immutable private results."""

import argparse
import json
from pathlib import Path
from .artifacts import verify_bundle
from .config import freeze_schedule


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("command", choices=["plan", "run", "inspect", "audit"])
    p.add_argument("--manifest", type=Path)
    p.add_argument("--expected-sha256")
    p.add_argument(
        "--run", type=Path, help="Sealed parent run for fixed-weight interventions"
    )
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--smoke", action="store_true")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--secondary", action="store_true")
    group.add_argument("--transformer", action="store_true")
    p.add_argument(
        "--features",
        choices=["relative", "levels", "correlation", "kmeans", "som"],
        default="relative",
    )
    args = p.parse_args()
    if args.smoke and (
        args.secondary or args.transformer or args.features != "relative"
    ):
        p.error(
            "smoke is the fixed primary SPY diagnostic; use separate full secondary stages"
        )
    if args.command == "inspect":
        print(json.dumps(verify_bundle(args.output)))
        return
    if args.manifest is None or not args.expected_sha256:
        p.error("manifest and expected-sha256 are required")
    from equity_lab.data.sequence_daily import load_daily_snapshot
    from .samples import build_samples
    from .protocol import make_folds
    from .runner import run_study
    from .config import SECONDARY

    snapshot = load_daily_snapshot(args.manifest, args.expected_sha256)
    if args.command == "audit":
        if args.run is None:
            p.error("audit requires --run")
        from .interventions import audit_fitted_models

        records = audit_fitted_models(snapshot, args.run, args.output)
        print(json.dumps(dict(status="completed", interventions=len(records))))
        return
    samples = build_samples(
        snapshot,
        60 if (args.secondary or args.transformer) else 20,
        symbols=["SPY"] if args.smoke else None,
        feature_mode="relative" if args.features == "relative" else "levels",
    )
    folds = make_folds(samples)
    if args.smoke:
        folds = folds[:1]
    schedule = freeze_schedule(
        len(folds),
        seeds=[11] if args.smoke else None,
        candidates=["cash", "holding", "sparse"]
        if args.smoke
        else ["matched", "equal", "dense", "sparse"]
        if args.features != "relative"
        else ["matched", "equal", "transformer_dense", "transformer_sparse"]
        if args.transformer
        else [n for n in SECONDARY if not n.startswith("transformer")]
        if args.secondary
        else None,
        max_fits=240
        if (args.secondary or args.transformer or args.features != "relative")
        else 600,
        seconds=600 if args.smoke else 21600,
        epochs=1 if args.smoke else 50,
    )
    schedule["selector"] = (
        args.features if args.features in ["correlation", "kmeans", "som"] else "all"
    )
    if args.command == "plan":
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(schedule, indent=2))
        print(
            json.dumps(
                dict(
                    fits=schedule["fits"],
                    tasks=len(schedule["tasks"]),
                    folds=len(folds),
                )
            )
        )
    else:
        import signal

        def interrupted(signum, frame):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, interrupted)
        summary = run_study(schedule, snapshot, samples, folds, args.output)
        print(
            json.dumps(
                dict(
                    status=summary["status"],
                    completed=len(summary["completed"]),
                    pending=len(summary["pending"]),
                )
            )
        )
        if summary["status"] != "completed":
            raise SystemExit(2)


if __name__ == "__main__":
    main()
