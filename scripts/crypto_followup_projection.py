"""Closed aggregate projection of immutable follow-up research evidence."""

import argparse
import hashlib
import math
import statistics
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

KINDS = ["ridge", "single", "matched", "equal", "dense"]
FEES = [0, 10, 25]
SOURCE_KEYS = {"audit", "diagnostics", "comparison", "plan", "projection_code"}
FORWARD_KEYS = {
    "as_of",
    "prefix_head",
    "prefix_receipts",
    "committed",
    "scored",
    "pending",
    "mature_unscored",
    "observed_bars",
    "revisions",
    "late_received_bars",
    "mse",
    "prior_mse",
    "skill",
    "deadline_violations",
    "score_reconstruction_violations",
}
METRICS = {"mse", "skill", "net_return", "exposure", "turnover", "max_drawdown"}
ROW_KEYS = {
    "fold",
    "kind",
    "seed",
    "rule",
    "hurdle",
    "fee_bps",
    "parameters",
    "fit_samples",
    "validation_samples",
    "test_samples",
} | METRICS
AGG_KEYS = {
    "kind",
    "rule",
    "fee_bps",
    "cases",
    "net_return",
    "min_return",
    "max_return",
    "skill",
    "exposure",
    "turnover",
    "max_drawdown",
}
DIAG_KEYS = {
    "step_hours",
    "fold",
    "model",
    "count",
    "prediction_quantiles",
    "target_quantiles",
    "above_hurdles",
}


def fields(value, keys):
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("PUBLIC_FIELDS")


def number(value, nullable=False):
    if value is None and nullable:
        return
    if type(value) not in [int, float] or not math.isfinite(value):
        raise ValueError("PUBLIC_NUMBER")


def validate_comparison(value):
    if (
        value.get("status") != "completed"
        or value.get("fits_started") != 39
        or value.get("fits_completed") != 39
        or not 0 <= value.get("elapsed_seconds", math.inf) < 900
        or len(value.get("rows", [])) != 234
    ):
        raise ValueError("INCOMPLETE_COMPARISON")
    expected = {
        (f, k, s, r, fee)
        for f in range(3)
        for k in KINDS
        for s in ([0] if k == "ridge" else [11, 29, 47])
        for r in ["fixed", "validation"]
        for fee in FEES
    }
    actual = set()
    for row in value["rows"]:
        fields(row, ROW_KEYS)
        actual.add(tuple(row[k] for k in ["fold", "kind", "seed", "rule", "fee_bps"]))
        for k in ROW_KEYS - {"kind", "rule"}:
            number(row[k], k == "skill")
        if row["hurdle"] not in [0, 0.001, 0.002] or (
            row["rule"] == "fixed" and row["hurdle"] != 0.002
        ):
            raise ValueError("PUBLIC_HURDLE")
        if (
            not 0 <= row["exposure"] <= 1
            or row["turnover"] < 0
            or not -1 <= row["max_drawdown"] <= 0
            or min(
                row[k] for k in ["fit_samples", "validation_samples", "test_samples"]
            )
            <= 1
        ):
            raise ValueError("PUBLIC_METRIC")
    if actual != expected:
        raise ValueError("PUBLIC_CASE_SCOPE")


def validate_public(x):
    fields(
        x,
        {
            "schema",
            "as_of",
            "scope",
            "sources",
            "forward",
            "diagnostics",
            "comparison",
            "provider",
        },
    )
    if (
        x["schema"] != "crypto.followup_public.v1"
        or x["scope"] != "retrospective_exploration_not_fresh_holdout"
    ):
        raise ValueError("PUBLIC_SCOPE")
    fields(x["sources"], SOURCE_KEYS)
    for v in x["sources"].values():
        if (
            not isinstance(v, str)
            or len(v) != 64
            or any(c not in "0123456789abcdef" for c in v)
        ):
            raise ValueError("PUBLIC_HASH")
    fields(x["forward"], FORWARD_KEYS)
    f = x["forward"]
    if (
        not isinstance(f["prefix_head"], str)
        or len(f["prefix_head"]) != 64
        or any(c not in "0123456789abcdef" for c in f["prefix_head"])
    ):
        raise ValueError("PUBLIC_PREFIX_HASH")
    for k in FORWARD_KEYS - {"as_of", "prefix_head"}:
        number(f[k], k in ["mse", "prior_mse", "skill"])
    if (
        f["committed"] != f["scored"] + f["pending"] + f["mature_unscored"]
        or f["deadline_violations"]
        or f["score_reconstruction_violations"]
    ):
        raise ValueError("PUBLIC_FORWARD")
    fields(x["diagnostics"], {"quantile_levels", "hurdles", "rows"})
    d = x["diagnostics"]
    if (
        d["quantile_levels"] != [0, 0.01, 0.1, 0.5, 0.9, 0.99, 1]
        or d["hurdles"] != [0, 0.001, 0.002]
        or len(d["rows"]) != 30
    ):
        raise ValueError("PUBLIC_DIAGNOSTIC_SCOPE")
    for r in d["rows"]:
        fields(r, DIAG_KEYS)
        number(r["count"])
        if r["count"] <= 0 or int(r["count"]) != r["count"]:
            raise ValueError("PUBLIC_DIAGNOSTIC_COUNT")
        if (
            r["step_hours"] not in [1, 4]
            or r["fold"] not in range(3)
            or r["model"]
            not in [
                "price_only",
                "prior",
                "factor_proxy_24h",
                "factor_delayed_72h",
                "factor_shift_7d",
            ]
        ):
            raise ValueError("PUBLIC_DIAGNOSTIC_SCOPE")
        for k, n in [
            ("prediction_quantiles", 7),
            ("target_quantiles", 7),
            ("above_hurdles", 3),
        ]:
            if len(r[k]) != n:
                raise ValueError("PUBLIC_DISTRIBUTION")
            for v in r[k]:
                number(v)
        if (
            sorted(r["prediction_quantiles"]) != r["prediction_quantiles"]
            or sorted(r["target_quantiles"]) != r["target_quantiles"]
            or any(not 0 <= v <= 1 for v in r["above_hurdles"])
        ):
            raise ValueError("PUBLIC_DISTRIBUTION")
    c = x["comparison"]
    fields(
        c,
        {
            "status",
            "fits_started",
            "fits_completed",
            "elapsed_seconds",
            "architecture",
            "rows",
            "aggregates",
            "gates",
            "source_revision",
        },
    )
    validate_comparison(c)
    fields(c["architecture"], set(KINDS))
    if len(c["source_revision"]) != 40 or any(
        v not in "0123456789abcdef" for v in c["source_revision"]
    ):
        raise ValueError("PUBLIC_REVISION")
    for k, v in c["architecture"].items():
        number(v)
    if len(c["aggregates"]) != 30 or len(c["gates"]) != 36:
        raise ValueError("PUBLIC_AGGREGATE_SCOPE")
    for r in c["aggregates"]:
        fields(r, AGG_KEYS)
        if (
            r["kind"] not in KINDS
            or r["rule"] not in ["fixed", "validation"]
            or r["fee_bps"] not in FEES
        ):
            raise ValueError("PUBLIC_AGGREGATE_SCOPE")
        for k in AGG_KEYS - {"kind", "rule"}:
            number(r[k], k == "skill")
    for r in c["gates"]:
        fields(r, {"fold", "kind", "seed", "mean_weights", "entropy"})
        if (
            r["kind"] not in KINDS[1:]
            or r["seed"] not in [11, 29, 47]
            or r["fold"] not in range(3)
        ):
            raise ValueError("PUBLIC_GATE_SCOPE")
        if len(r["mean_weights"]) != (3 if r["kind"] in ["dense", "equal"] else 1):
            raise ValueError("PUBLIC_GATE_SCOPE")
        for v in r["mean_weights"]:
            number(v)
        if (
            any(v < 0 or v > 1 for v in r["mean_weights"])
            or abs(sum(r["mean_weights"]) - 1) > 1e-4
        ):
            raise ValueError("PUBLIC_GATE_WEIGHTS")
        number(r["entropy"])
        if r["entropy"] < 0:
            raise ValueError("PUBLIC_GATE_ENTROPY")
    fields(
        x["provider"],
        {"reviewed_on", "definitions", "historical_availability", "revision_policy"},
    )
    if x["provider"] != dict(
        reviewed_on="2026-11-07",
        definitions={
            "CO-A-02-03": "documented",
            "CO-S-01-01": "documented",
            "CO-S-01-05": "unverified",
        },
        historical_availability="unverified",
        revision_policy="unverified",
    ):
        raise ValueError("PUBLIC_PROVIDER")
    # No arbitrary text/path slots: every descriptive string is a fixed enum, date or hash.
    for key in ["as_of"]:
        datetime.fromisoformat(x[key])
    datetime.fromisoformat(f["as_of"])
    if datetime.fromisoformat(f["as_of"]) > datetime.fromisoformat(x["as_of"]):
        raise ValueError("PUBLIC_CLOCK")


def project(audit, diagnostics, comparison, plan):
    for p in [audit, diagnostics, comparison, plan]:
        verify_seal(p)
    a = read_json(audit / "audit.json")
    d = read_json(diagnostics / "diagnostics.json")
    c = read_json(comparison / "summary.json")
    p = read_json(plan / "plan.json")
    validate_comparison(c)
    if (
        c["plan_sha256"] != digest(plan / "plan.json")
        or p["source_revision"] != c["source_revision"]
        or p["study_seal"] != d["study_seal"]
    ):
        raise ValueError("SOURCE_SCOPE_CHANGED")
    aggregates = []
    for kind in KINDS:
        for rule in ["fixed", "validation"]:
            for fee in FEES:
                rows = [
                    r
                    for r in c["rows"]
                    if r["kind"] == kind and r["rule"] == rule and r["fee_bps"] == fee
                ]
                aggregates.append(
                    dict(
                        kind=kind,
                        rule=rule,
                        fee_bps=fee,
                        cases=len(rows),
                        net_return=statistics.median(r["net_return"] for r in rows),
                        min_return=min(r["net_return"] for r in rows),
                        max_return=max(r["net_return"] for r in rows),
                        skill=statistics.mean(r["skill"] for r in rows),
                        exposure=statistics.mean(r["exposure"] for r in rows),
                        turnover=statistics.mean(r["turnover"] for r in rows),
                        max_drawdown=min(r["max_drawdown"] for r in rows),
                    )
                )
    x = dict(
        schema="crypto.followup_public.v1",
        as_of=datetime.now(timezone.utc).isoformat(),
        scope=c["scope"],
        sources=dict(
            audit=digest(audit / "seal.json"),
            diagnostics=digest(diagnostics / "seal.json"),
            comparison=digest(comparison / "seal.json"),
            plan=digest(plan / "seal.json"),
            projection_code=hashlib.sha256(
                Path(__file__).read_text().replace("\r\n", "\n").encode()
            ).hexdigest(),
        ),
        forward={k: a[k] for k in FORWARD_KEYS},
        diagnostics={k: d[k] for k in ["quantile_levels", "hurdles", "rows"]},
        comparison={
            **{
                k: c[k]
                for k in [
                    "status",
                    "fits_started",
                    "fits_completed",
                    "elapsed_seconds",
                    "architecture",
                    "rows",
                    "gates",
                    "source_revision",
                ]
            },
            "aggregates": aggregates,
        },
        provider=dict(
            reviewed_on="2026-11-07",
            definitions={
                "CO-A-02-03": "documented",
                "CO-S-01-01": "documented",
                "CO-S-01-05": "unverified",
            },
            historical_availability="unverified",
            revision_policy="unverified",
        ),
    )
    validate_public(x)
    return x


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for k in ["audit", "diagnostics", "comparison", "plan", "output"]:
        p.add_argument("--" + k, type=Path, required=True)
    a = p.parse_args()
    x = project(a.audit, a.diagnostics, a.comparison, a.plan)
    out = new_output(a.output, inputs=[a.audit, a.diagnostics, a.comparison, a.plan])
    write_json(out / "crypto-followup.v1.json", x)
    seal(out)
    print("published aggregate rows", len(x["comparison"]["rows"]))


if __name__ == "__main__":
    main()
