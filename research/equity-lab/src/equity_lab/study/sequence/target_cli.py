"""Frozen target-scheme plan/run/analyze and modeled forward-calendar preparation."""

import argparse
from datetime import date, timedelta
import importlib.metadata
import json
from pathlib import Path
import signal
from equity_lab.data.sequence_daily import (
    load_daily_snapshot,
    strict_json,
    digest,
    session_schedule,
)
from .artifacts import (
    write_json,
    create_bundle,
    seal_bundle,
    verify_bundle,
    source_identity,
)
from .samples import build_samples
from .protocol import make_folds
from .target_study import freeze_target_schedule, run_target_study
from .target_analysis import analyze_targets


def external(path):
    path = path.resolve()
    if any((p / ".git").exists() for p in [path, *path.parents]):
        raise ValueError("OUTPUT_MUST_BE_EXTERNAL")
    return path


def future_calendar(start, end):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first > last:
        raise ValueError("INVALID_CALENDAR_WINDOW")
    schedule = session_schedule(start, (last + timedelta(days=14)).isoformat())
    signals = schedule.loc[start:end]
    if signals.empty:
        raise ValueError("NO_SIGNAL_SESSIONS")
    tail = schedule.loc[schedule.index > signals.index[-1]].iloc[:2]
    if len(tail) != 2:
        raise ValueError("MISSING_FINAL_OPENS")
    return dict(
        schema="equity_lab.sequence_forward_calendar.v1",
        calendar="XNYS",
        timezone="America/New_York",
        package="exchange_calendars",
        package_version=importlib.metadata.version("exchange-calendars"),
        signal_start=start,
        signal_end=end,
        sessions=[
            dict(date=day, open=str(row.open), close=str(row.close))
            for day, row in signals.iterrows()
        ],
        final_entry=dict(date=tail.index[0], open=str(tail.iloc[0].open)),
        final_exit=dict(date=tail.index[1], open=str(tail.iloc[1].open)),
        observed_availability=False,
        registered_holdout=False,
    )


def analyze_run(parent, output):
    parent = Path(parent)
    verify_bundle(parent)
    bound = digest(parent / "checksums.json")
    summary = strict_json(parent / "summary.json")
    if summary.get("schema") != "equity_lab.sequence_target_study.v1":
        raise ValueError("INVALID_TARGET_PARENT")
    create_bundle(
        output,
        dict(
            schema="equity_lab.sequence_target_analysis.v1",
            parent_checksums_sha256=bound,
            source=source_identity(),
        ),
    )
    report = dict(status="partial", reason="INTERRUPTED")
    try:
        report = analyze_targets(summary)
        verify_bundle(parent)
        if digest(parent / "checksums.json") != bound:
            raise ValueError("PARENT_CHANGED")
        write_json(output / "analysis.json", report)
        rows = [
            "# Target-scheme exploratory report",
            "",
            "Previously exposed fixed-current history; no acceptance or execution authorization.",
            "",
            "| Objective | Model | Prediction skill | Mean daily rank IC | Fixed5bps return* | Selected5bps return* |",
            "|---|---|---:|---:|---:|---:|",
        ]

        def fmt(v):
            return "undefined" if v is None else f"{v:.5f}"

        for objective, result in report["objectives"].items():
            for name, m in result["models"].items():
                rows.append(
                    f"| {objective} | {name} | {fmt(m['mean_prediction_skill'])} | {fmt(m['mean_daily_rank_ic'])} | {m['accounts']['fixed_5']['median_fold_seed_mean_return']:.2%} | {m['accounts']['validation_5']['median_fold_seed_mean_return']:.2%} |"
                )
            rows.extend(
                [
                    "",
                    f"{objective} continuation: {result['continuation']['status']}; expansion=false.",
                    "",
                ]
            )
        rows += [
            "*Median across folds of seed-mean fold returns; not continuous NAV.",
            "",
            "The schemes change target, loss and policy hurdle together. Validation also informed early stopping. Intervals use20-session blocks,2000draws and same-date seed averaging without multiplicity correction. All candidate/objective IDs remain frozen for forward preparation without winner selection.",
        ]
        (output / "report.md").write_text("\n".join(rows) + "\n")
    except KeyboardInterrupt:
        write_json(output / "analysis.json", report)
    except Exception:
        report = dict(status="invalid", reason="ANALYSIS_OR_PARENT_INVALID")
        write_json(output / "analysis.json", report)
        raise
    finally:
        seal_bundle(output)
    return report


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("command", choices=["plan", "run", "analyze", "calendar"])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", default="2026-11-09")
    parser.add_argument("--end", default="2027-02-05")
    args = parser.parse_args()
    output = external(args.output)

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    if args.command == "calendar":
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x") as stream:
            json.dump(future_calendar(args.start, args.end), stream, indent=2)
        return
    if args.command == "analyze":
        if args.run is None:
            parser.error("analyze requires --run")
        result = analyze_run(args.run, output)
    else:
        if args.manifest is None or not args.expected_sha256:
            parser.error("manifest and expected-sha256 required")
        snapshot = load_daily_snapshot(args.manifest, args.expected_sha256)
        samples = build_samples(snapshot, 20)
        folds = make_folds(samples)
        if args.command == "plan":
            plan = freeze_target_schedule(len(folds))
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x") as stream:
                json.dump(plan, stream, indent=2)
            print(
                json.dumps(
                    dict(fits=plan["fits"], tasks=len(plan["tasks"]), folds=len(folds))
                )
            )
            return
        if args.plan is None:
            parser.error("run requires --plan")
        result = run_target_study(
            strict_json(args.plan), snapshot, samples, folds, output
        )
    print(json.dumps(dict(status=result["status"])))
    if result["status"] != "completed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
