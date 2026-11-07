"""Read-only local research health; no network, promotion, scheduler or messages."""

import argparse
import json
import html
from datetime import datetime, timezone
from pathlib import Path
from competition_tools.crypto_evidence import (
    verify_seal,
    read_json,
    digest,
    new_output,
    seal,
)
from competition_tools.datasets.storage import write_json
from competition_tools.datasets.binance_intraday import verify_intraday
from .crypto_observation import observation_history, instant


def monitor(dataset, study, protocol, *, as_of):
    report = dict(
        schema="crypto.research_monitor.v1",
        as_of=as_of.isoformat(),
        status="evidence_incomplete",
        acquisition=None,
        study=None,
        observation=None,
        blocking_reasons=[],
        accepted_research=False,
        execution_authorized=False,
    )
    for name, path in [
        ("acquisition", Path(dataset)),
        ("study", Path(study)),
        ("observation", Path(protocol)),
    ]:
        try:
            verify_seal(path)
            if name == "acquisition":
                value = verify_intraday(path)
                report[name] = dict(
                    status=value["status"],
                    coverage=value["coverage"],
                    budget=value["budget"],
                    last_historical_bar=value["end_exclusive"],
                    seal_sha256=digest(path / "seal.json"),
                )
                if value["status"] != "completed":
                    report["blocking_reasons"].append("acquisition_incomplete")
            elif name == "study":
                value = read_json(path / "summary.json")
                report[name] = dict(
                    status=value["status"],
                    fit_count=value["fit_count"],
                    expected_fits=value["expected_fits"],
                    trial_count=value["trial_count"],
                    elapsed_seconds=value["elapsed_seconds"],
                    verified_factor_arm=value["verified_factor_arm"],
                    seal_sha256=digest(path / "seal.json"),
                )
                if value["status"] != "completed":
                    report["blocking_reasons"].append("study_incomplete")
            else:
                frozen, history = observation_history(path)
                last = history[-1][1] if history else None
                if as_of < instant(frozen["frozen_at"]):
                    raise ValueError("MONITOR_CLOCK_BEFORE_FREEZE")
                times = []
                for p, _ in history:
                    if (p / "market.json").exists():
                        times.extend(
                            instant(r["interval_end"])
                            for rows in read_json(p / "market.json")["prices"].values()
                            for r in rows
                        )
                report[name] = dict(
                    frozen_at=frozen["frozen_at"],
                    captures=len(history),
                    http_attempts=sum(r["http"]["attempts"] for _, r in history),
                    transferred_bytes=sum(r["http"]["bytes"] for _, r in history),
                    observed_bars=sum(len(r["observed_bars"]) for _, r in history),
                    late_received_bars=sum(
                        len(r.get("late_received_bars", [])) for _, r in history
                    ),
                    committed_forecasts=sum(
                        len(r["committed_forecasts"]) for _, r in history
                    ),
                    scored_forecasts=sum(
                        len(r["scored_forecasts"]) for _, r in history
                    ),
                    revisions=sum(len(r["revisions"]) for _, r in history),
                    last_capture_at=last["captured_at"] if last else None,
                    last_receipt_seal_sha256=digest(history[-1][0] / "seal.json")
                    if history
                    else None,
                    last_capture_status=last["status"] if last else "awaiting_capture",
                    market_age_hours=(as_of - max(times)).total_seconds() / 3600
                    if times
                    else None,
                    factor_forecasting=frozen["factor_forecasting"],
                    seal_sha256=digest(path / "seal.json"),
                )
                if last and last["status"] != "completed":
                    report["blocking_reasons"].append("last_capture_partial")
        except (OSError, ValueError, KeyError, TypeError):
            report["blocking_reasons"].append(name + "_missing_or_invalid")
            report[name] = None
    if any(report[k] is None for k in ["acquisition", "study", "observation"]):
        report["status"] = "blocked"
    report["scientific_limits"] = [
        "historical_factor_publication_and_revision_unverified",
        "retrospective_three_fold_screen",
        "prospective_outcomes_not_yet_established",
    ]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ["dataset", "study", "protocol"]:
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = monitor(
        args.dataset, args.study, args.protocol, as_of=datetime.now(timezone.utc)
    )
    if args.output:
        output = new_output(
            args.output, inputs=[args.dataset, args.study, args.protocol]
        )
        write_json(output / "monitor.json", value)
        rendered = html.escape(json.dumps(value, indent=2))
        (output / "index.html").write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Crypto research health</title><style>body{max-width:1000px;margin:2rem auto;padding:1rem;font-family:system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>Crypto research health</h1><p>Read-only evidence status. Captured bars, committed forecasts and scored forecasts are distinct. No execution authorization.</p><pre>'
            + rendered
            + "</pre></html>"
        )
        seal(output)
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
