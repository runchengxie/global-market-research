"""Freeze preparation records and map candidate evidence; never certify a holdout."""

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from competition_tools.datasets.research_evidence import (
    audit_daily_research_evidence,
    _read,
)
from competition_tools.datasets.storage import digest
from .sequence_governance import build_protocol, REQUIREMENTS


def validate_calendar(calendar, now):
    try:
        if (
            calendar["schema"] != "equity_lab.sequence_forward_calendar.v1"
            or calendar["calendar"] != "XNYS"
            or calendar["timezone"] != "America/New_York"
            or calendar["package"] != "exchange_calendars"
            or calendar["package_version"] != "4.13.2"
            or calendar["observed_availability"] is not False
            or calendar["registered_holdout"] is not False
        ):
            raise ValueError
        start, end = (
            date.fromisoformat(calendar["signal_start"]),
            date.fromisoformat(calendar["signal_end"]),
        )
        if now.tzinfo is None or not now.date() < start <= end:
            raise ValueError
        sessions = calendar["sessions"]
        days = [date.fromisoformat(s["date"]) for s in sessions]
        if not days or days != sorted(set(days)) or days[0] != start or days[-1] != end:
            raise ValueError

        def stamp(value, day):
            parsed = datetime.fromisoformat(value)
            if parsed.utcoffset() is None or parsed.date() != day:
                raise ValueError
            return parsed

        last = None
        for day, row in zip(days, sessions):
            opened = stamp(row["open"], day)
            closed = stamp(row["close"], day)
            if (
                day.weekday() > 4
                or not opened < closed
                or (last is not None and not last < opened)
            ):
                raise ValueError
            last = closed
        for key in ["final_entry", "final_exit"]:
            row = calendar[key]
            day = date.fromisoformat(row["date"])
            opened = stamp(row["open"], day)
            if day.weekday() > 4 or not last < opened:
                raise ValueError
            last = opened
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError("INVALID_FORWARD_CALENDAR") from None
    return calendar


def _validate_plan(plan):
    try:
        if (
            plan["schema"] != "equity_lab.sequence_target_plan.v1"
            or plan["folds"] != 7
            or plan["seeds"] != [11, 23, 37]
            or plan["fits"] != 140
            or plan["max_fits"] != 180
            or plan["seconds"] != 21600
            or plan["epochs"] != 30
            or plan["batch_size"] != 128
            or plan["patience"] != 5
            or plan["hurdles"] != {"classification": 0.5, "regression": 0.001}
            or plan["thresholds"]
            != {
                "classification": [0.35, 0.425, 0.5, 0.575, 0.65],
                "regression": [0, 0.0005, 0.001, 0.002, 0.004],
            }
        ):
            raise ValueError
        expected = {
            (f, o, m, s, int(m != "prior"))
            for f in range(7)
            for o in ["classification", "regression"]
            for m in ["prior", "linear", "matched", "equal", "sparse"]
            for s in ([11] if m in ["prior", "linear"] else [11, 23, 37])
        } | {
            (f, "control", m, 0, 0)
            for f in range(7)
            for m in ["cash", "holding", "volatility10"]
        }
        actual = {
            (t["fold"], t["objective"], t["model"], t["seed"], t["fits"])
            for t in plan["tasks"]
        }
        if (
            actual != expected
            or len(plan["tasks"]) != len(expected)
            or sum(t["fits"] for t in plan["tasks"]) != 140
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("INVALID_FROZEN_TARGET_PLAN") from None


def build_preparation(evidence, calendar, plan, now):
    validate_calendar(calendar, now)
    _validate_plan(plan)
    protocol = build_protocol(
        evidence, calendar["signal_start"], calendar["signal_end"], now
    )
    return dict(
        schema="competition.sequence_preparation.v1",
        status="frozen_preparation_blocked",
        created_at=now.astimezone(timezone.utc).isoformat(),
        registered_holdout=False,
        accepted_research=False,
        execution_authorized=False,
        candidate_selection="all_frozen_candidates_no_retrospective_winner_selection",
        candidates=[
            dict(objective=o, model=m)
            for o in ["classification", "regression"]
            for m in ["prior", "linear", "matched", "equal", "sparse"]
        ],
        common_controls=["cash", "holding", "volatility10"],
        features="relative10-v1",
        lookback=20,
        horizon="next_open_to_following_open",
        source_manifest_sha256=evidence["manifest_sha256"],
        signal_start=calendar["signal_start"],
        signal_end=calendar["signal_end"],
        modeled_signal_sessions=len(calendar["sessions"]),
        final_entry=calendar["final_entry"],
        final_exit=calendar["final_exit"],
        required_evidence=protocol["required_evidence"],
        plan=plan,
        forward_preconditions=[
            "Fresh immutable snapshot through the required feature cutoff; current retrospective snapshot is not future data",
            "Independent source publication/availability and action/security-identity records",
            "Owner-reviewed prospective access/exposure record and explicit acceptance; preparation is not registration",
        ],
        stopping_rules=protocol["stopping_rules"] | dict(max_fits=180),
        publication_scope="Owner authorization for aggregate reports does not establish raw provider redistribution rights",
        prohibitions=protocol["prohibitions"],
    )


def candidate_matrix(manifest, evidence):
    return dict(
        schema="competition.sequence_candidate_evidence.v1",
        status="blocked",
        accepted_research=False,
        execution_authorized=False,
        checks=evidence["checks"],
        observed_facts=dict(
            source=manifest["spec"]["source"],
            price_basis_claim=manifest["spec"]["price_basis"],
            universe_status_claim=manifest["spec"]["universe_status"],
            receipt_observed_at=manifest["receipt"]["observed_at"],
            receipt_scope="Acquisition timestamp is not historical daily feature availability",
        ),
        requirements=[
            dict(
                code=code,
                status="blocked",
                needed=needed,
                candidate_files=["manifest.json", "receipt.json"],
                candidate_quality="Producer metadata only; no independent closure",
                next_action={
                    "POINT_IN_TIME_UNIVERSE_UNVERIFIED": "Obtain dated membership and historical eligibility with stable IDs",
                    "HISTORICAL_SECURITY_IDENTITY_UNVERIFIED": "Obtain issuer/exchange mappings, symbol changes and delistings with effective dates",
                    "CORPORATE_ACTION_COVERAGE_UNVERIFIED": "Obtain action/dividend coverage and reconcile the split-adjusted price-unit convention",
                    "HISTORICAL_AVAILABILITY_UNVERIFIED": "Retain provider publication/acquisition records at each causal cutoff",
                    "OWNER_PROVENANCE_UNVERIFIED": "Obtain independently reviewable owner/source-use terms bound to the exact input bytes",
                    "HOLDOUT_GOVERNANCE_UNVERIFIED": "Create reviewed future access/exposure governance after requirements are met; do not relabel old history",
                }[code],
            )
            for code, needed in REQUIREMENTS.items()
        ],
    )


def main():
    p = argparse.ArgumentParser(__doc__)
    for name in ["manifest", "calendar", "plan", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    for name in [
        "expected-sha256",
        "calendar-sha256",
        "plan-sha256",
        "source-revision",
    ]:
        p.add_argument("--" + name, required=True)
    args = p.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(args.manifest.parent.resolve()) or any(
        (a / ".git").exists() for a in [output, *output.parents]
    ):
        raise ValueError("OUTPUT_MUST_BE_EXTERNAL")
    bindings = {
        name: dict(path=str(path.resolve()), sha256=digest(path))
        for name, path in [
            ("manifest", args.manifest),
            ("receipt", args.manifest.parent / "receipt.json"),
            ("calendar", args.calendar),
            ("plan", args.plan),
        ]
    }
    if (
        bindings["manifest"]["sha256"] != args.expected_sha256
        or bindings["calendar"]["sha256"] != args.calendar_sha256
        or bindings["plan"]["sha256"] != args.plan_sha256
    ):
        raise ValueError("READINESS_BINDING_MISMATCH")
    evidence = audit_daily_research_evidence(args.manifest, args.expected_sha256)
    calendar = _read(args.calendar)
    plan = _read(args.plan)
    preparation = build_preparation(
        evidence, calendar, plan, datetime.now(timezone.utc)
    )
    preparation["source_revision"] = args.source_revision
    preparation["bindings"] = bindings
    matrix = candidate_matrix(_read(args.manifest), evidence)
    # Recheck every bound file and owner data after constructing the packet.
    audit_daily_research_evidence(args.manifest, args.expected_sha256)
    if any(digest(Path(item["path"])) != item["sha256"] for item in bindings.values()):
        raise ValueError("READINESS_INPUT_CHANGED")
    output.mkdir(parents=True, exist_ok=False)
    for name, value in [
        ("preparation.json", preparation),
        ("candidate-evidence.json", matrix),
        ("owner-audit.json", evidence),
    ]:
        with (output / name).open("x") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
    checksums = {
        f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in output.iterdir()
    }
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                status=preparation["status"],
                signal_sessions=len(calendar["sessions"]),
                blockers=6,
            )
        )
    )


if __name__ == "__main__":
    main()
