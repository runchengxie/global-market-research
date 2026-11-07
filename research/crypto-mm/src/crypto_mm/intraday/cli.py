"""Explicit offline crypto evidence commands; inputs and outputs remain external."""

import argparse
import json
from pathlib import Path
from .inputs import sha
from .study import freeze_screen, run_screen


def fingerprint():
    import numpy
    import sklearn

    return dict(
        schema="crypto.producer_fingerprint.v1",
        files={p.name: sha(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        numpy=numpy.__version__,
        sklearn=sklearn.__version__,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--dataset", type=Path, required=True)
    freeze.add_argument("--sentiment", type=Path, required=True)
    freeze.add_argument("--sentiment-sha256", required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--source-revision", required=True)
    run = sub.add_parser("run")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    sub.add_parser("fingerprint")
    args = parser.parse_args()
    if args.command == "freeze":
        value = freeze_screen(
            args.dataset,
            args.sentiment,
            args.sentiment_sha256,
            args.output,
            args.source_revision,
        )
    elif args.command == "run":
        result = run_screen(args.plan, args.output)
        value = {
            k: result[k]
            for k in [
                "status",
                "fit_count",
                "trial_count",
                "elapsed_seconds",
                "verified_factor_arm",
            ]
        }
    else:
        value = fingerprint()
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
