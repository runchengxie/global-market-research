"""Offline sequence study: plan, run and verify immutable private results."""

import argparse
import json
from pathlib import Path
from .artifacts import verify_bundle
from .config import freeze_schedule


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("command", choices=["plan", "run", "inspect"])
    p.add_argument("--manifest", type=Path)
    p.add_argument("--expected-sha256")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--secondary", action="store_true")
    args = p.parse_args()
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
    samples = build_samples(
        snapshot, 60 if args.secondary else 20, symbols=["SPY"] if args.smoke else None
    )
    folds = make_folds(samples)
    if args.smoke:
        folds = folds[:1]
    schedule = freeze_schedule(
        len(folds),
        seeds=[11] if args.smoke else None,
        candidates=["cash", "holding", "sparse"]
        if args.smoke
        else SECONDARY
        if args.secondary
        else None,
        max_fits=240 if args.secondary else 600,
        seconds=600 if args.smoke else 21600,
        epochs=1 if args.smoke else 50,
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
