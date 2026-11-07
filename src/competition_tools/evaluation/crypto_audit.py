"""Read-only reconstruction of a sealed prospective receipt prefix."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
from math import isclose, isfinite
from competition_tools.crypto_evidence import digest, new_output, read_json, seal
from competition_tools.datasets.storage import write_json
from .crypto_observation import observation_history, instant


def audit_receipts(rows, as_of):
    forecasts, scores = {}, {}
    previous = None
    observed = revisions = 0
    for receipt, market in rows:
        captured = instant(receipt["captured_at"])
        if captured > as_of or (previous and captured < previous):
            raise ValueError("AUDIT_CLOCK")
        previous = captured
        # Scores must bind to an earlier receipt, not a forecast in this batch.
        for score in receipt["scored_forecasts"]:
            key = score["forecast_id"]
            if key not in forecasts:
                raise ValueError("UNKNOWN_FORECAST")
            if key in scores:
                raise ValueError("DUPLICATE_SCORE")
            f = forecasts[key]
            scored = instant(score["scored_at"])
            if not instant(f["exit_at"]) <= scored <= captured:
                raise ValueError("SCORE_DEADLINE")
            openings = {
                instant(r["time_open"]): r["open"]
                for r in market["prices"].get(f["asset"], [])
            }
            try:
                target = (
                    openings[instant(f["exit_at"])] / openings[instant(f["entry_at"])]
                    - 1
                )
            except KeyError as exc:
                raise ValueError("SCORE_PRICE_MISSING") from exc
            expected = dict(
                target=target,
                squared_error=(target - f["prediction"]) ** 2,
                prior_squared_error=(target - f["prior_prediction"]) ** 2,
            )
            if any(
                not isfinite(score[k])
                or not isclose(score[k], v, abs_tol=1e-12, rel_tol=1e-10)
                for k, v in expected.items()
            ):
                raise ValueError("SCORE_RECONSTRUCTION")
            scores[key] = score
        for f in receipt["committed_forecasts"]:
            if f["id"] in forecasts:
                raise ValueError("DUPLICATE_FORECAST")
            if (
                not instant(f["feature_cutoff"])
                <= instant(f["generated_at"])
                <= captured
                < instant(f["entry_at"])
                < instant(f["exit_at"])
            ):
                raise ValueError("FORECAST_DEADLINE")
            forecasts[f["id"]] = f
        observed += len(receipt["observed_bars"])
        revisions += len(receipt["revisions"])
    values = list(scores.values())

    def mean(k):
        return sum(s[k] for s in values) / len(values) if values else None

    prior = mean("prior_squared_error")
    mse = mean("squared_error")
    return dict(
        committed=len(forecasts),
        scored=len(scores),
        pending=sum(
            instant(f["exit_at"]) > as_of
            for k, f in forecasts.items()
            if k not in scores
        ),
        mature_unscored=sum(
            instant(f["exit_at"]) <= as_of
            for k, f in forecasts.items()
            if k not in scores
        ),
        observed_bars=observed,
        revisions=revisions,
        mse=mse,
        prior_mse=prior,
        skill=1 - mse / prior if prior and mse is not None else None,
        deadline_violations=0,
        score_reconstruction_violations=0,
    )


def audit_protocol(protocol, as_of):
    protocol = Path(protocol)
    if protocol.with_name(protocol.name + ".captures.lock").exists():
        raise ValueError("CAPTURE_IN_PROGRESS_TRY_LATER")
    frozen, history = observation_history(protocol)
    rows = [
        (
            r,
            read_json(p / "market.json")
            if (p / "market.json").exists()
            else {"prices": {}},
        )
        for p, r in history
        if instant(r["captured_at"]) <= as_of
    ]
    prefix = history[: len(rows)]
    result = audit_receipts(rows, as_of)
    return dict(
        schema="crypto.forward_audit.v1",
        as_of=as_of.isoformat(),
        prefix_receipts=len(rows),
        prefix_head=digest(prefix[-1][0] / "seal.json") if prefix else None,
        protocol_seal=digest(protocol / "seal.json"),
        effective_budget=frozen["budget"],
        http_attempts=sum(r["http"]["attempts"] for _, r in prefix),
        transferred_bytes=sum(r["http"]["bytes"] for _, r in prefix),
        late_received_bars=sum(len(r.get("late_received_bars", [])) for _, r in prefix),
        **result,
        scope="engineering_acceptance_only",
        accepted_research=False,
        execution_authorized=False,
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--protocol", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    result = audit_protocol(a.protocol, datetime.now(timezone.utc))
    out = new_output(a.output, inputs=[a.protocol])
    write_json(out / "audit.json", result)
    seal(out)
    print(result)


if __name__ == "__main__":
    main()
