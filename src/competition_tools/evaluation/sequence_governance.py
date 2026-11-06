"""Read-only evidence crosswalk and future protocol DRAFT, never an acceptance."""

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from competition_tools.datasets.research_evidence import (
    audit_daily_research_evidence,
    BLOCKERS,
)

REQUIREMENTS = {
    "POINT_IN_TIME_UNIVERSE_UNVERIFIED": "Dated universe membership with stable identities and independently evidenced availability.",
    "HISTORICAL_SECURITY_IDENTITY_UNVERIFIED": "Issuer/exchange/provider identity mappings, effective dates, delistings and symbol changes.",
    "CORPORATE_ACTION_COVERAGE_UNVERIFIED": "Complete split/dividend/action coverage, price basis and cash-flow rules; no adjusted-price/dividend double count.",
    "HISTORICAL_AVAILABILITY_UNVERIFIED": "Independent source publication/acquisition evidence and causal availability cutoffs.",
    "OWNER_PROVENANCE_UNVERIFIED": "Trusted owner protocol and source-use/publication rights bound to exact bytes.",
    "HOLDOUT_GOVERNANCE_UNVERIFIED": "Owner review, candidate freeze, access/exposure record, calendar and future data acceptance.",
}


def build_protocol(evidence, start, end, now):
    expected = [dict(code="RETAINED_BYTES_VERIFIED", status="passed")] + [
        dict(code=k, status="blocked") for k in BLOCKERS
    ]
    if (
        evidence.get("schema") != "competition.daily_research_evidence_gap.v1"
        or evidence.get("status") != "blocked"
        or evidence.get("accepted_research") is not False
        or evidence.get("execution_authorized") is not False
        or evidence.get("checks") != expected
    ):
        raise ValueError("INVALID_OWNER_EVIDENCE")
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if now.tzinfo is None or not now.date() < first <= last:
        raise ValueError("INVALID_FUTURE_WINDOW")
    return dict(
        schema="competition.sequence_future_protocol_draft.v1",
        status="draft_pending_owner_review",
        created_at=now.astimezone(timezone.utc).isoformat(),
        proposed_signal_date_start=start,
        proposed_signal_date_end=end,
        source_manifest_sha256=evidence["manifest_sha256"],
        accepted_research=False,
        execution_authorized=False,
        candidates=[
            "cash",
            "holding",
            "constant_25",
            "constant_50",
            "causal_volatility_10",
            "validation_exposure",
            "validation_volatility",
            "logistic",
            "matched",
            "equal",
            "dense",
            "sparse",
            "validation_threshold",
        ],
        feature_version="relative10-v1",
        lookback=20,
        label="open[t+2]/open[t+1]-1 > 0.002",
        cutoff=0.5,
        threshold_candidates=[0.35, 0.425, 0.5, 0.575, 0.65],
        selection="validation only; report all attempted candidates",
        fit_sessions=400,
        validation_sessions=80,
        test_sessions=63,
        seeds=[11, 23, 37, 53, 71],
        primary_fee_bps=5,
        guardrail_fee_bps=20,
        signal="close plus15m availability proxy; independently evidenced availability required",
        readiness_allowance_hours=12,
        required_evidence=[
            dict(code=k, status="blocked", needed=REQUIREMENTS[k]) for k in BLOCKERS
        ],
        stopping_rules=dict(
            max_fits=100,
            max_seconds=21600,
            stop_new_signals_at=end,
            final_exit="Require the second following exchange open after the last signal; no silent truncation",
            stop_on=[
                "input_revision",
                "missing_session_or_exit",
                "unverified_action_boundary",
                "budget_exhausted",
            ],
            extension="No extension based on observed performance; changes require a new owner-reviewed protocol version",
        ),
        prohibitions=[
            "No research reservation or trusted owner record created",
            "No scheduled collection or broker calls",
            "No old dates relabeled as untouched",
            "No automatic promotion by self-attestation",
        ],
    )


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    output = args.output.absolute()
    if output.resolve().is_relative_to(args.manifest.parent.resolve()) or any(
        (n / ".git").exists() for n in [output, *output.parents]
    ):
        raise ValueError("OUTPUT_MUST_BE_EXTERNAL")
    evidence = audit_daily_research_evidence(args.manifest, args.expected_sha256)
    draft = build_protocol(evidence, args.start, args.end, datetime.now(timezone.utc))
    output.mkdir(parents=True, exist_ok=False)
    for name, value in [
        ("evidence-crosswalk.json", evidence),
        ("future-protocol-draft.json", draft),
    ]:
        with (output / name).open("x") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
    checksums = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in output.iterdir()
        if p.is_file()
    }
    (output / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    print(json.dumps(dict(status=draft["status"], blocked_requirements=len(BLOCKERS))))


if __name__ == "__main__":
    main()
