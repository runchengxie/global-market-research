"""Explicit verified aggregate export; never upload raw archives or forecasts."""

import argparse
import hashlib
import json
import math
import re
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
from competition_tools.evaluation.crypto_observation import (
    instant,
    canonical_hash,
    observation_history,
)

ARMS = [
    "price_only",
    "factor_proxy_24h",
    "factor_delayed_72h",
    "factor_shift_7d",
    "prior",
    "cash",
    "holding",
    "trend",
]
ROW_KEYS = {
    "step_hours",
    "arm",
    "fee_bps",
    "folds",
    "net_return",
    "skill",
    "ic",
    "exposure",
    "turnover",
    "max_drawdown",
    "paired_mean",
    "paired_interval",
}
FOLD_KEYS = {
    "step_hours",
    "fold",
    "arm",
    "fee_bps",
    "bars",
    "mse",
    "skill",
    "ic",
    "net_return",
    "exposure",
    "turnover",
    "max_drawdown",
}


def projection_code_hash():
    return hashlib.sha256(
        Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()


def keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("PUBLIC_FIELDS_NOT_ALLOWLISTED")


def number(value, nullable=False):
    if nullable and value is None:
        return
    if type(value) not in [int, float] or not math.isfinite(value):
        raise ValueError("PUBLIC_NUMBER_INVALID")


def validate_public(value):
    keys(
        value,
        [
            "schema",
            "scope",
            "accepted_research",
            "execution_authorized",
            "sample",
            "experiment",
            "rows",
            "folds",
            "observation",
            "operations",
            "sources",
        ],
    )
    if (
        value["schema"] != "crypto.research_public.v1"
        or value["scope"]
        != "retrospective_proxy_screen_with_unreviewed_forward_receipts"
        or value["accepted_research"] is not False
        or value["execution_authorized"] is not False
    ):
        raise ValueError("PUBLIC_EVIDENCE_STAGE_INVALID")
    sample = value["sample"]
    keys(
        sample,
        [
            "products",
            "start",
            "end_exclusive",
            "quote_currency",
            "price_basis",
            "hourly_per_asset",
            "four_hour_per_asset",
            "factor_rows",
            "factor_grain",
            "factor_start",
            "factor_end_exclusive",
            "factor_indicators",
            "factor_availability",
        ],
    )
    if (
        sample["products"] != ["BTCUSDT", "ETHUSDT"]
        or sample["quote_currency"] != "USDT"
        or sample["price_basis"] != "raw"
        or sample["hourly_per_asset"] != 17520
        or sample["four_hour_per_asset"] != 4380
        or sample["factor_grain"] != "1d"
        or sample["factor_rows"] != 2280
        or sample["factor_availability"]
        != "historical_publication_and_revision_unverified"
        or sample["factor_indicators"] != ["CO-A-02-03", "CO-S-01-01", "CO-S-01-05"]
    ):
        raise ValueError("PUBLIC_SAMPLE_MISMATCH")
    for k in ["start", "end_exclusive", "factor_start", "factor_end_exclusive"]:
        instant(sample[k])
    experiment = value["experiment"]
    keys(
        experiment,
        [
            "fit_count",
            "expected_fits",
            "trial_count",
            "fold_count",
            "fees",
            "hurdle",
            "execution_delay_bars",
            "factor_proxy_delays_hours",
            "test_windows",
            "verified_factor_arm",
        ],
    )
    if (
        experiment["fit_count"] != 24
        or experiment["expected_fits"] != 24
        or experiment["trial_count"] != 144
        or experiment["fold_count"] != 3
        or experiment["fees"] != [0, 10, 25]
        or experiment["hurdle"] != 0.002
        or experiment["execution_delay_bars"] != 1
        or experiment["factor_proxy_delays_hours"] != [24, 72, 192]
        or experiment["verified_factor_arm"] != "blocked"
    ):
        raise ValueError("PUBLIC_PROTOCOL_MISMATCH")
    if len(experiment["test_windows"]) != 3:
        raise ValueError("PUBLIC_FOLD_SCOPE")
    for a, b in experiment["test_windows"]:
        if instant(a) >= instant(b):
            raise ValueError("PUBLIC_WINDOW_ORDER")
    if len(value["rows"]) != 48 or len(value["folds"]) != 144:
        raise ValueError("PUBLIC_CASE_COUNT")
    for table, allowed in [("rows", ROW_KEYS), ("folds", FOLD_KEYS)]:
        seen = set()
        for r in value[table]:
            keys(r, allowed)
            if (
                r["step_hours"] not in [1, 4]
                or r["arm"] not in ARMS
                or r["fee_bps"] not in [0, 10, 25]
            ):
                raise ValueError("PUBLIC_CASE_ID")
            identifier = (r["step_hours"], r["arm"], r["fee_bps"], r.get("fold"))
            if identifier in seen:
                raise ValueError("PUBLIC_DUPLICATE_CASE")
            seen.add(identifier)
            for name in [
                "net_return",
                "skill",
                "ic",
                "exposure",
                "turnover",
                "max_drawdown",
            ]:
                number(r[name], nullable=name in ["skill", "ic"])
            if (
                not 0 <= r["exposure"] <= 1
                or not -1 <= r["max_drawdown"] <= 0
                or r["net_return"] <= -1
                or r["turnover"] < 0
                or (r["ic"] is not None and not -1 <= r["ic"] <= 1)
            ):
                raise ValueError("PUBLIC_METRIC_RANGE")
            if table == "rows":
                if r["folds"] != 3 or len(r["paired_interval"]) != 2:
                    raise ValueError("PUBLIC_INTERVAL_SCOPE")
                for x in [r["paired_mean"], *r["paired_interval"]]:
                    number(x)
                if r["paired_interval"][0] > r["paired_interval"][1]:
                    raise ValueError("PUBLIC_INTERVAL_ORDER")
            elif (
                r["fold"] not in [0, 1, 2]
                or type(r["bars"]) is not int
                or r["bars"] <= 0
            ):
                raise ValueError("PUBLIC_FOLD_ID")
            else:
                number(r["mse"], nullable=True)
    observation = value["observation"]
    keys(
        observation,
        [
            "frozen_at",
            "as_of",
            "captures",
            "observed_bars",
            "late_received_bars",
            "committed_forecasts",
            "scored_forecasts",
            "revisions",
            "last_capture_at",
            "last_capture_status",
            "market_age_hours",
            "factor_forecasting",
            "mode",
        ],
    )
    for k in ["frozen_at", "as_of"]:
        instant(observation[k])
    if observation["last_capture_at"] is not None:
        instant(observation["last_capture_at"])
    for k in [
        "captures",
        "observed_bars",
        "late_received_bars",
        "committed_forecasts",
        "scored_forecasts",
        "revisions",
    ]:
        if type(observation[k]) is not int or observation[k] < 0:
            raise ValueError("PUBLIC_OBSERVATION_COUNT")
    if (
        observation["scored_forecasts"] > observation["committed_forecasts"]
        or observation["mode"] != "self_recorded_unreviewed_capture"
        or observation["last_capture_status"]
        not in ["completed", "partial", "awaiting_capture"]
    ):
        raise ValueError("PUBLIC_FORWARD_STAGE")
    number(observation["market_age_hours"], nullable=True)
    if (
        observation["factor_forecasting"]
        != "blocked_stale_and_unknown_historical_availability"
    ):
        raise ValueError("PUBLIC_FACTOR_STAGE")
    operations = value["operations"]
    keys(
        operations,
        [
            "http_attempts",
            "http_limit",
            "transfer_bytes",
            "transfer_limit",
            "fit_limit",
            "observation_http_attempts",
            "observation_http_limit",
            "reserved_unknown_bytes",
            "health_status",
        ],
    )
    for k, v in operations.items():
        if k == "health_status":
            continue
        if type(v) is not int or v < 0:
            raise ValueError("PUBLIC_BUDGET_NUMBER")
    if (
        operations["http_attempts"] > operations["http_limit"]
        or operations["transfer_bytes"] > operations["transfer_limit"]
        or operations["fit_limit"] != 36
        or operations["observation_http_attempts"]
        > operations["observation_http_limit"]
    ):
        raise ValueError("PUBLIC_BUDGET_MISMATCH")
    if operations["health_status"] not in [
        "blocked",
        "evidence_incomplete",
        "completed",
    ]:
        raise ValueError("PUBLIC_HEALTH_STATE")
    sources = value["sources"]
    keys(
        sources,
        [
            "acquisition_revision",
            "fit_revision",
            "dataset_seal",
            "study_seal",
            "protocol_seal",
            "monitor_seal",
            "factor_snapshot",
            "producer_fingerprint",
            "projection_code",
            "budget_debit",
            "receipt_chain_head",
        ],
    )
    for k, v in sources.items():
        if k in ["budget_debit", "receipt_chain_head"] and v is None:
            continue
        if not isinstance(v, str) or not re.fullmatch(
            "[a-f0-9]{" + ("40" if k.endswith("_revision") else "64") + "}", v
        ):
            raise ValueError("PUBLIC_SOURCE_ID")
    encoded = json.dumps(value, allow_nan=False)
    if any(
        x in encoded
        for x in [
            "/home/",
            "/run/media/",
            "file://",
            "credential",
            "raw_prices",
            "individual_predictions",
        ]
    ):
        raise ValueError("PRIVATE_PUBLICATION_CONTENT")
    return value


def project(dataset, study, protocol, monitor):
    dataset, study, protocol, monitor = map(Path, [dataset, study, protocol, monitor])
    for p in [dataset, study, protocol, monitor]:
        verify_seal(p)
    data = verify_intraday(dataset)
    result = read_json(study / "summary.json")
    plan = read_json(study / "plan.json")
    frozen = read_json(protocol / "protocol.json")
    health = read_json(monitor / "monitor.json")
    if (
        data["status"] != "completed"
        or result["status"] != "completed"
        or result["fit_count"] != 24
        or result["trial_count"] != 144
        or plan["dataset_seal_sha256"] != digest(dataset / "seal.json")
        or frozen["dataset_seal_sha256"] != digest(dataset / "seal.json")
        or frozen["study_seal_sha256"] != digest(study / "seal.json")
    ):
        raise ValueError("PUBLIC_SOURCE_INCOMPLETE_OR_MISMATCH")
    if (
        health["acquisition"] is None
        or health["study"] is None
        or health["observation"] is None
        or health["acquisition"]["seal_sha256"] != digest(dataset / "seal.json")
        or health["study"]["seal_sha256"] != digest(study / "seal.json")
        or health["observation"]["seal_sha256"] != digest(protocol / "seal.json")
    ):
        raise ValueError("PUBLIC_MONITOR_SCOPE_MISMATCH")
    factor = Path(plan["sentiment"])
    if digest(factor) != plan["sentiment_sha256"]:
        raise ValueError("FACTOR_SOURCE_CHANGED")
    factors = read_json(factor)
    observed = health["observation"]
    effective, _ = observation_history(protocol)
    parent = effective.get("predecessor") or {}
    coverage = data["coverage"]
    if any(coverage[p] != coverage["BTCUSDT"] for p in ["BTCUSDT", "ETHUSDT"]):
        raise ValueError("PUBLIC_PRICE_COVERAGE")
    value = dict(
        schema="crypto.research_public.v1",
        scope="retrospective_proxy_screen_with_unreviewed_forward_receipts",
        accepted_research=False,
        execution_authorized=False,
        sample=dict(
            products=data["products"],
            start=data["start"],
            end_exclusive=data["end_exclusive"],
            quote_currency=data["quote_currency"],
            price_basis=data["price_basis"],
            hourly_per_asset=coverage["BTCUSDT"]["1h"],
            four_hour_per_asset=coverage["BTCUSDT"]["4h"],
            factor_rows=len(factors),
            factor_grain="1d",
            factor_start=min(r["period_start_utc"] for r in factors),
            factor_end_exclusive=max(r["period_end_utc"] for r in factors),
            factor_indicators=["CO-A-02-03", "CO-S-01-01", "CO-S-01-05"],
            factor_availability="historical_publication_and_revision_unverified",
        ),
        experiment=dict(
            fit_count=result["fit_count"],
            expected_fits=result["expected_fits"],
            trial_count=result["trial_count"],
            fold_count=3,
            fees=plan["fees"],
            hurdle=0.002,
            execution_delay_bars=1,
            factor_proxy_delays_hours=[24, 72, 192],
            test_windows=plan["folds"],
            verified_factor_arm="blocked",
        ),
        rows=[{k: r[k] for k in sorted(ROW_KEYS)} for r in result["summary"]],
        folds=[{k: r[k] for k in sorted(FOLD_KEYS)} for r in result["folds"]],
        observation={
            k: observed[k]
            for k in [
                "frozen_at",
                "captures",
                "observed_bars",
                "late_received_bars",
                "committed_forecasts",
                "scored_forecasts",
                "revisions",
                "last_capture_at",
                "last_capture_status",
                "market_age_hours",
                "factor_forecasting",
            ]
        },
        operations=dict(
            http_attempts=data["budget"]["attempts"],
            http_limit=112,
            transfer_bytes=data["budget"]["transferred_bytes"],
            transfer_limit=32 * 1024**2,
            fit_limit=36,
            observation_http_attempts=observed["http_attempts"]
            + parent.get("http_attempts_charged", 0),
            observation_http_limit=96,
            reserved_unknown_bytes=parent.get("reserved_unknown_bytes", 0),
            health_status=health["status"],
        ),
        sources=dict(
            acquisition_revision=data["source_revision"],
            fit_revision=result["source_revision"],
            dataset_seal=digest(dataset / "seal.json"),
            study_seal=digest(study / "seal.json"),
            protocol_seal=digest(protocol / "seal.json"),
            monitor_seal=digest(monitor / "seal.json"),
            factor_snapshot=plan["sentiment_sha256"],
            producer_fingerprint=canonical_hash(frozen["producer_fingerprint"]),
            projection_code=projection_code_hash(),
            receipt_chain_head=observed["last_receipt_seal_sha256"],
            budget_debit=digest(
                protocol.with_name(protocol.name + ".budget-debit") / "seal.json"
            )
            if protocol.with_name(protocol.name + ".budget-debit").exists()
            else None,
        ),
    )
    value["observation"].update(
        as_of=health["as_of"], mode="self_recorded_unreviewed_capture"
    )
    validate_public(value)
    for p in [dataset, study, protocol, monitor]:
        verify_seal(p)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ["dataset", "study", "protocol", "monitor", "output"]:
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    inputs = [args.dataset, args.study, args.protocol, args.monitor]
    value = project(*inputs)
    output = new_output(args.output, inputs=inputs)
    write_json(output / "crypto-evidence.v1.json", value)
    seal(output)
    print(json.dumps(dict(status="completed", fits=24, public_cases=144, rows=48)))


if __name__ == "__main__":
    main()
