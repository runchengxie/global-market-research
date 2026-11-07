"""Explicit commands for bounded retrospective follow-up; no broker or scheduler."""

import argparse
import json
from pathlib import Path
from .study import freeze_comparison, run_comparison, new_output
from .diagnostics import diagnose_scores
from ..intraday.inputs import write, seal


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    for k in ["dataset", "study", "output"]:
        f.add_argument("--" + k, type=Path, required=True)
    f.add_argument("--source-revision", required=True)
    r = sub.add_parser("run")
    r.add_argument("--plan", type=Path, required=True)
    r.add_argument("--output", type=Path, required=True)
    d = sub.add_parser("diagnose")
    d.add_argument("--study", type=Path, required=True)
    d.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.command == "freeze":
        value = freeze_comparison(a.dataset, a.study, a.output, a.source_revision)
    elif a.command == "run":
        value = run_comparison(a.plan, a.output)
        print(
            json.dumps(
                {
                    k: value[k]
                    for k in [
                        "status",
                        "fits_started",
                        "fits_completed",
                        "elapsed_seconds",
                    ]
                }
            )
        )
        raise SystemExit(0 if value["status"] == "completed" else 2)
    else:
        value = diagnose_scores(a.study)
        out = new_output(a.output, [a.study])
        write(out / "diagnostics.json", value)
        seal(out)
    print(json.dumps(value))


if __name__ == "__main__":
    main()
