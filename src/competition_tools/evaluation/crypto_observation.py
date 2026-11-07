"""Manual immutable market receipts and pre-outcome offline forecasts; no broker."""

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from competition_tools.crypto_evidence import (
    digest,
    read_json,
    new_output,
    seal,
    verify_seal,
)
from competition_tools.datasets.daily_storage import safe_path
from competition_tools.datasets.storage import write_json
from competition_tools.datasets.binance_daily_transport import NoRedirect, run_worker
from competition_tools.datasets.binance_intraday import PRODUCTS


def utc():
    return datetime.now(timezone.utc)


def instant(value):
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.utcoffset() != timedelta(0):
        raise ValueError("UTC_REQUIRED")
    return t


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, allow_nan=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def _producer(python, args, *, timeout=30):
    result = subprocess.run(
        [str(python), "-m", "crypto_mm.intraday.cli", *args],
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode or len(result.stdout) > 128 * 1024:
        raise ValueError("OFFLINE_PRODUCER_FAILED")
    return json.loads(result.stdout)


def freeze_observation(study, dataset, python, output, *, now, previous_protocol=None):
    study = safe_path(Path(study))
    dataset = safe_path(Path(dataset))
    verify_seal(study)
    verify_seal(dataset)
    summary = read_json(study / "summary.json")
    plan = read_json(study / "plan.json")
    if (
        summary["status"] != "completed"
        or summary["fit_count"] != 24
        or digest(dataset / "seal.json") != plan["dataset_seal_sha256"]
        or now.utcoffset() != timedelta(0)
    ):
        raise ValueError("INVALID_OBSERVATION_SOURCE")
    fingerprint = _producer(python, ["fingerprint"])
    models = {}
    for step in [1, 4]:
        file = study / "models" / f"{step}h-2-price_only.json"
        model = read_json(file)
        if (
            model["arm"] != "price_only"
            or model["step_hours"] != step
            or instant(model["fit_last_exit"]) >= now
        ):
            raise ValueError("MODEL_NOT_FROZEN_IN_PAST")
        models[f"price_only-{step}h"] = dict(
            file=str(file),
            sha256=digest(file),
            fit_source_revision=summary["source_revision"],
        )
    budget = dict(
        captures=48,
        http_attempts=96,
        transferred_bytes=32 * 1024**2,
        per_capture_seconds=60,
        per_response_bytes=1024**2,
    )
    predecessor = None
    previous_inputs = []
    if previous_protocol is not None:
        previous = safe_path(Path(previous_protocol))
        verify_seal(previous)
        old = read_json(previous / "protocol.json")
        old_root = safe_path(Path(old["capture_root"]))
        if (
            old_root != previous.with_name(previous.name + ".captures")
            or old_root.with_name(old_root.name + ".lock").exists()
        ):
            raise ValueError("PREDECESSOR_ACTIVE_OR_INVALID")
        if {k: v["sha256"] for k, v in old["models"].items()} != {
            k: v["sha256"] for k, v in models.items()
        }:
            raise ValueError("PREDECESSOR_MODEL_CHANGED")
        used = 0
        used_bytes = 0
        reserved = 0
        seals = []
        for index, folder in enumerate(sorted(old_root.iterdir()), 1):
            if folder.name != f"{index:06d}":
                raise ValueError("PREDECESSOR_UNKNOWN_STATE")
            verify_seal(folder)
            receipt = read_json(folder / "receipt.json")
            if (
                receipt["protocol_sha256"] != digest(previous / "protocol.json")
                or receipt["committed_forecasts"]
                or receipt["scored_forecasts"]
                or instant(receipt["captured_at"]) > now
            ):
                raise ValueError("PREDECESSOR_NOT_EMPTY_FAILED_START")
            used += receipt["http"]["attempts"]
            used_bytes += receipt["http"]["bytes"]
            reserved += old["budget"]["per_response_bytes"] * int(
                receipt["http"]["unknown_spend"]
            )
            seals.append(digest(folder / "seal.json"))
        budget = dict(old["budget"])
        budget["captures"] -= len(seals)
        budget["http_attempts"] -= used
        budget["transferred_bytes"] -= used_bytes + reserved
        if (
            min(
                budget["captures"], budget["http_attempts"], budget["transferred_bytes"]
            )
            <= 0
        ):
            raise ValueError("PREDECESSOR_BUDGET_EXHAUSTED")
        predecessor = dict(
            protocol_sha256=digest(previous / "protocol.json"),
            capture_seals=seals,
            http_attempts_charged=used,
            transferred_bytes_charged=used_bytes,
            reserved_unknown_bytes=reserved,
        )
        previous_inputs = [previous, old_root]
    output = new_output(output, inputs=[study, dataset, *previous_inputs])
    captures = output.with_name(output.name + ".captures")
    captures.mkdir(exist_ok=False)
    value = dict(
        schema="crypto.observation_protocol.v1",
        frozen_at=now.isoformat(),
        known_market_cutoff=read_json(dataset / "manifest.json")["end_exclusive"],
        models=models,
        producer_python=str(Path(python).absolute()),
        producer_fingerprint=fingerprint,
        capture_root=str(captures),
        dataset_seal_sha256=digest(dataset / "seal.json"),
        study_seal_sha256=digest(study / "seal.json"),
        factor_forecasting="blocked_stale_and_unknown_historical_availability",
        budget=budget,
        predecessor=predecessor,
        accepted_research=False,
        execution_authorized=False,
    )
    write_json(output / "protocol.json", value)
    seal(output)
    return value


def validate_forecasts(protocol, rows, committed_at):
    expected = {
        "candidate",
        "asset",
        "feature_cutoff",
        "generated_at",
        "entry_at",
        "exit_at",
        "prediction",
        "prior_prediction",
        "feature_sha256",
        "checkpoint_sha256",
    }
    seen = set()
    for r in rows:
        if (
            set(r) != expected
            or r["candidate"] not in protocol["models"]
            or r["asset"] not in PRODUCTS
        ):
            raise ValueError("INVALID_FORECAST_FIELDS")
        cutoff, generated, entry, exit = (
            instant(r[k])
            for k in ["feature_cutoff", "generated_at", "entry_at", "exit_at"]
        )
        step = int(r["candidate"].split("-")[-1].removesuffix("h"))
        if (
            not instant(protocol["frozen_at"]) <= generated <= committed_at < entry
            or cutoff > generated
            or entry - cutoff != timedelta(hours=step)
            or exit - entry != timedelta(hours=step)
        ):
            raise ValueError("FORECAST_NOT_PRE_OUTCOME")
        if (
            any(
                type(r[k]) not in [int, float] or not math.isfinite(r[k])
                for k in ["prediction", "prior_prediction"]
            )
            or r["checkpoint_sha256"] != protocol["models"][r["candidate"]]["sha256"]
            or not re.fullmatch("[a-f0-9]{64}", r["feature_sha256"])
        ):
            raise ValueError("INVALID_FORECAST_BINDING")
        key = (r["candidate"], r["asset"], r["entry_at"])
        if key in seen:
            raise ValueError("DUPLICATE_FORECAST")
        seen.add(key)
    return rows


def recent_url(product):
    if product not in PRODUCTS:
        raise ValueError("INVALID_RECENT_PRODUCT")
    return (
        "https://data-api.binance.vision/api/v3/klines?symbol="
        + product
        + "&interval=1h&limit=1000"
    )


class RecentTransport:
    def fetch(self, url, *, max_bytes, timeout):
        if url not in [recent_url(p) for p in PRODUCTS]:
            raise ValueError("UNAPPROVED_RECENT_URL")
        return run_worker(
            [
                sys.executable,
                "-m",
                "competition_tools.evaluation.crypto_observation",
                "worker",
                url,
                str(max_bytes),
                str(timeout),
            ],
            max_bytes=max_bytes,
            timeout=timeout,
        )


def normalize_recent(body, product, received):
    rows = json.loads(body)
    out = []
    if not isinstance(rows, list) or not 170 <= len(rows) <= 1000:
        raise ValueError("RECENT_HISTORY_TOO_SHORT")
    previous = None
    for r in rows:
        if not isinstance(r, list) or len(r) != 12:
            raise ValueError("INVALID_RECENT_COLUMNS")
        opening = int(r[0])
        t = datetime.fromtimestamp(opening / 1000, timezone.utc)
        end = t + timedelta(hours=1)
        if (
            t.minute
            or t.second
            or t.microsecond
            or int(r[6]) != opening + 3600000 - 1
            or (previous and t != previous)
        ):
            raise ValueError("INVALID_RECENT_GRID_OR_UNIT")
        previous = end
        values = list(map(float, r[1:6]))
        o, h, low, c, v = values
        if (
            not all(math.isfinite(x) for x in values)
            or min(o, h, low, c) <= 0
            or v < 0
            or not low <= min(o, c) <= max(o, c) <= h
        ):
            raise ValueError("INVALID_RECENT_OHLCV")
        if end <= received:
            out.append(
                dict(
                    asset=product,
                    time_open=t.isoformat(),
                    interval_end=end.isoformat(),
                    open=o,
                    high=h,
                    low=low,
                    close=c,
                    volume=v,
                )
            )
    if len(out) < 170 or received - instant(out[-1]["interval_end"]) >= timedelta(
        hours=2
    ):
        raise ValueError("RECENT_HISTORY_NOT_FRESH_OR_COMPLETE")
    return out


def observation_history(protocol_dir):
    protocol_dir = safe_path(Path(protocol_dir))
    verify_seal(protocol_dir)
    protocol = read_json(protocol_dir / "protocol.json")
    root = safe_path(Path(protocol["capture_root"]))
    if root != protocol_dir.with_name(protocol_dir.name + ".captures"):
        raise ValueError("INVALID_CAPTURE_ROOT")
    result = []
    previous = None
    for index, p in enumerate(sorted(root.iterdir()), 1):
        if p.name != f"{index:06d}" or not p.is_dir():
            raise ValueError("UNKNOWN_OBSERVATION_STATE")
        verify_seal(p)
        r = read_json(p / "receipt.json")
        if (
            r["protocol_sha256"] != digest(protocol_dir / "protocol.json")
            or r["previous_seal_sha256"] != previous
        ):
            raise ValueError("OBSERVATION_CHAIN_CHANGED")
        validate_forecasts(
            protocol,
            [
                {k: v for k, v in row.items() if k != "id"}
                for row in r["committed_forecasts"]
            ],
            instant(r["captured_at"]),
        )
        for row in r["committed_forecasts"]:
            if row["id"] != canonical_hash(
                [r["protocol_sha256"], row["candidate"], row["asset"], row["entry_at"]]
            ):
                raise ValueError("FORECAST_ID_CHANGED")
        if r["http"]["unknown_spend"]:
            raise ValueError("UNKNOWN_OBSERVATION_SPEND")
        previous = digest(p / "seal.json")
        result.append((p, r))
    return protocol, result


def capture_observation(protocol_dir, transport, *, clock=utc):
    capture_started = time.monotonic()
    protocol_dir = safe_path(Path(protocol_dir))
    verify_seal(protocol_dir)
    protocol = read_json(protocol_dir / "protocol.json")
    root = safe_path(Path(protocol["capture_root"]))
    lock = root.with_name(root.name + ".lock")
    with lock.open("x") as f:
        os.chmod(lock, 0o600)
        f.write(str(os.getpid()))
    lock_inode = lock.stat().st_ino
    output = None
    try:
        protocol, history = observation_history(protocol_dir)
        budget = protocol["budget"]
        total_attempts = sum(r["http"]["attempts"] for _, r in history)
        total_bytes = sum(r["http"]["bytes"] for _, r in history)
        if (
            len(history) >= budget["captures"]
            or total_attempts + 2 > budget["http_attempts"]
        ):
            raise ValueError("OBSERVATION_BUDGET")
        if history and instant(history[-1][1]["captured_at"]) > clock():
            raise ValueError("CLOCK_REGRESSION")
        if (
            _producer(
                protocol["producer_python"],
                ["fingerprint"],
                timeout=min(
                    30,
                    max(
                        0.01,
                        budget["per_capture_seconds"]
                        - (time.monotonic() - capture_started),
                    ),
                ),
            )
            != protocol["producer_fingerprint"]
        ):
            raise ValueError("FROZEN_PRODUCER_CHANGED")
        output = new_output(root / f"{len(history) + 1:06d}", inputs=[protocol_dir])
        started = capture_started
        http = dict(attempts=0, bytes=0, unknown_spend=False)
        prices = {}
        forecasts = []
        scores = []
        observed = []
        revisions = []
        blocked = []
        state = "running"
        reason = None
        try:
            for product in PRODUCTS:
                remaining = budget["per_capture_seconds"] - (time.monotonic() - started)
                limit = min(
                    budget["per_response_bytes"],
                    budget["transferred_bytes"] - total_bytes - http["bytes"],
                )
                if remaining <= 0 or limit <= 0:
                    raise TimeoutError("CAPTURE_BUDGET")
                http["attempts"] += 1
                http["unknown_spend"] = True
                write_json(output / "http.json", http)
                status, body = transport.fetch(
                    recent_url(product), max_bytes=limit, timeout=min(20, remaining)
                )
                http["bytes"] += len(body)
                http["unknown_spend"] = False
                write_json(output / "http.json", http)
                (output / f"raw-{product}.json").write_bytes(body)
                if status != 200:
                    raise ValueError(f"RECENT_HTTP_{status}")
                prices[product] = normalize_recent(body, product, clock())
            retrieved = clock()
            market = dict(
                schema="crypto.capture_prices.v1",
                retrieved_at=retrieved.isoformat(),
                prices=prices,
            )
            write_json(output / "market.json", market)
            previous_observed = {}
            previous_forecasts = {}
            previous_scored = set()
            previous_bars = {}
            for p, r in history:
                previous_observed.update(
                    {(x["asset"], x["interval_end"]): x for x in r["observed_bars"]}
                )
                previous_forecasts.update(
                    {x["id"]: x for x in r["committed_forecasts"]}
                )
                previous_scored.update(x["forecast_id"] for x in r["scored_forecasts"])
                if (p / "market.json").exists():
                    for asset, rows in read_json(p / "market.json")["prices"].items():
                        previous_bars.update(
                            {
                                (asset, x["interval_end"]): canonical_hash(x)
                                for x in rows
                            }
                        )
            for asset, rows in prices.items():
                for row in rows:
                    key = (asset, row["interval_end"])
                    h = canonical_hash(row)
                    if key in previous_bars and previous_bars[key] != h:
                        revisions.append(
                            dict(
                                asset=asset,
                                interval_end=key[1],
                                previous_sha256=previous_bars[key],
                                received_sha256=h,
                            )
                        )
                    if (
                        instant(row["interval_end"]) > instant(protocol["frozen_at"])
                        and key not in previous_observed
                    ):
                        observed.append(
                            dict(
                                asset=asset,
                                interval_end=key[1],
                                received_at=retrieved.isoformat(),
                                data_sha256=h,
                            )
                        )
            generated = clock()
            candidate_file = output / "forecast-candidates.json"
            candidates = _producer(
                protocol["producer_python"],
                [
                    "forecast",
                    "--capture",
                    str(output / "market.json"),
                    "--capture-sha256",
                    digest(output / "market.json"),
                    "--protocol",
                    str(protocol_dir / "protocol.json"),
                    "--output",
                    str(candidate_file),
                    "--generated-at",
                    generated.isoformat(),
                ],
                timeout=min(
                    30,
                    max(
                        0.01,
                        budget["per_capture_seconds"]
                        - (time.monotonic() - capture_started),
                    ),
                ),
            )
            committed = clock()
            validate_forecasts(protocol, candidates["forecasts"], committed)
            blocked = candidates["blocked"]
            for row in candidates["forecasts"]:
                identifier = canonical_hash(
                    [
                        digest(protocol_dir / "protocol.json"),
                        row["candidate"],
                        row["asset"],
                        row["entry_at"],
                    ]
                )
                if identifier not in previous_forecasts:
                    forecasts.append(dict(row, id=identifier))
            # Validation expects the closed producer fields; receipt IDs are checked separately.
            openings = {
                a: {instant(x["time_open"]): x["open"] for x in rows}
                for a, rows in prices.items()
            }
            for identifier, row in previous_forecasts.items():
                if identifier in previous_scored:
                    continue
                entry, exit = instant(row["entry_at"]), instant(row["exit_at"])
                bars = openings[row["asset"]]
                if exit > committed or entry not in bars or exit not in bars:
                    continue
                target = bars[exit] / bars[entry] - 1
                scores.append(
                    dict(
                        forecast_id=identifier,
                        scored_at=committed.isoformat(),
                        target=target,
                        squared_error=(target - row["prediction"]) ** 2,
                        prior_squared_error=(target - row["prior_prediction"]) ** 2,
                    )
                )
            if time.monotonic() - capture_started >= budget["per_capture_seconds"]:
                raise TimeoutError("CAPTURE_DEADLINE")
            state = "completed"
        except (Exception, KeyboardInterrupt) as exc:
            state = "partial"
            reason = type(exc).__name__ + ":" + str(exc)
        captured = clock()
        try:
            validate_forecasts(
                protocol,
                [{k: v for k, v in row.items() if k != "id"} for row in forecasts],
                captured,
            )
        except ValueError:
            forecasts = []
            state = "partial"
            reason = "FORECAST_ENTRY_DEADLINE"
        receipt = dict(
            schema="crypto.observation_receipt.v1",
            status=state,
            reason=reason,
            protocol_sha256=digest(protocol_dir / "protocol.json"),
            previous_seal_sha256=digest(history[-1][0] / "seal.json")
            if history
            else None,
            captured_at=captured.isoformat(),
            http=http,
            observed_bars=observed,
            committed_forecasts=forecasts,
            scored_forecasts=scores,
            revisions=revisions,
            forecast_blocking_reasons=blocked,
            factor_forecasting=protocol["factor_forecasting"],
            accepted_research=False,
            execution_authorized=False,
        )
        write_json(output / "receipt.json", receipt)
        seal(output)
        return receipt
    finally:
        if lock.exists() and lock.stat().st_ino == lock_inode:
            lock.unlink()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        url, limit, timeout = sys.argv[2:]
        if url not in [recent_url(p) for p in PRODUCTS]:
            raise ValueError("UNAPPROVED_URL")
        try:
            response = urllib.request.build_opener(NoRedirect()).open(
                url, timeout=float(timeout)
            )
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            body = response.read(int(limit) + 1)
            status = response.status
        if len(body) > int(limit):
            raise ValueError("RESPONSE_TOO_LARGE")
        sys.stdout.buffer.write(int(status).to_bytes(4, "big") + body)
        return
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    for key in ["study", "dataset", "producer-python", "output"]:
        freeze.add_argument("--" + key, type=Path, required=True)
    freeze.add_argument("--previous-protocol", type=Path)
    capture = sub.add_parser("capture")
    capture.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        r = freeze_observation(
            args.study, args.dataset, args.producer_python, args.output, now=utc()
        )
        print(json.dumps({"schema": r["schema"], "frozen_at": r["frozen_at"]}))
    else:
        r = capture_observation(args.protocol, RecentTransport())
        print(
            json.dumps(
                dict(
                    status=r["status"],
                    observed_bars=len(r["observed_bars"]),
                    committed_forecasts=len(r["committed_forecasts"]),
                    scored_forecasts=len(r["scored_forecasts"]),
                    reason=r["reason"],
                )
            )
        )


if __name__ == "__main__":
    main()
