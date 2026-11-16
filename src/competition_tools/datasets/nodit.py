"""Manual research-only acquisition of two Ethereum daily statistics."""

import argparse
import csv
import hashlib
import io
import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .dex_spec import safe_path
from .nodit_transport import MAX_BYTES, METHODS, decode_json
from .storage import write_json

SCHEMA = "competition.nodit_statistics.v1"
FILES = {
    "plan.json",
    "receipt.json",
    "raw/active_accounts.json",
    "raw/transactions.json",
    "normalized.csv",
}


def _window(start, end, now):
    try:
        if not all(
            isinstance(x, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)
            for x in (start, end)
        ):
            raise ValueError
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError
        latest = (
            now.astimezone(timezone.utc) - timedelta(minutes=30)
        ).date() - timedelta(days=1)
        if not 0 <= (last - first).days < 100 or last > latest:
            raise ValueError
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise ValueError("NODIT_WINDOW_INVALID") from None
    return [str(first + timedelta(days=i)) for i in range((last - first).days + 1)]


def _budgets(requests, cu, seconds):
    if (
        type(requests) is not int
        or not 2 <= requests <= 4
        or type(cu) is not int
        or not 300 <= cu <= 600
        or type(seconds) is not int
        or not 1 <= seconds <= 120
    ):
        raise ValueError("NODIT_BUDGET_INVALID")


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("NODIT_TIMESTAMP_INVALID")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("NODIT_TIMESTAMP_INVALID")
    return result


def _series(body, dates):
    data = decode_json(body)
    if (
        not isinstance(data, dict)
        or set(data) - {"count", "items"}
        or not isinstance(data.get("items"), list)
    ):
        raise ValueError("NODIT_STATISTICS_INVALID")
    items = data["items"]
    rows = {}
    for row in items:
        if (
            not isinstance(row, dict)
            or set(row) != {"date", "count"}
            or not isinstance(row["date"], str)
            or row["date"] in rows
            or type(row["count"]) is not int
            or row["count"] < 0
        ):
            raise ValueError("NODIT_STATISTICS_INVALID")
        rows[row["date"]] = row["count"]
    if set(rows) != set(dates) or (
        "count" in data
        and (type(data["count"]) is not int or data["count"] != len(rows))
    ):
        raise ValueError("NODIT_COVERAGE_INVALID")
    return rows


def _csv(dates, series):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["date", *METHODS])
    writer.writerows([day, *[series[m][day] for m in METHODS]] for day in dates)
    return stream.getvalue().encode()


def _bytes(path, body):
    with path.open("xb") as stream:
        stream.write(body)
    path.chmod(0o600)


def _json(path, value):
    write_json(path, value)
    path.chmod(0o600)


def collect(
    start,
    end,
    output,
    *,
    transport,
    max_requests=4,
    max_cu=600,
    max_seconds=120,
    now=None,
    sleep=None,
):
    observed = now or datetime.now(timezone.utc)
    dates = _window(start, end, observed)
    _budgets(max_requests, max_cu, max_seconds)
    out = safe_path(Path(output))
    if out.exists():
        raise FileExistsError("NODIT_OUTPUT_EXISTS")
    out.mkdir(parents=True, mode=0o700)
    (out / "raw").mkdir(mode=0o700)
    plan = {
        "schema": SCHEMA,
        "chain": "ethereum",
        "network": "mainnet",
        "start": start,
        "end": end,
        "created_at": observed.isoformat(),
        "metrics": list(METHODS),
        "budget": {
            "max_requests": max_requests,
            "max_cu": max_cu,
            "max_seconds": max_seconds,
            "max_response_bytes": MAX_BYTES,
        },
        "estimated_cu_per_request": 150,
        "publication_delay_minutes": 30,
        "accepted_research": False,
        "execution_authorized": False,
    }
    _json(out / "plan.json", plan)
    state = {
        "schema": SCHEMA,
        "status": "reserved",
        "attempts": 0,
        "estimated_cu": 0,
        "spend_uncertain": False,
        "in_flight": False,
        "issue_code": None,
        "observations": [],
        "accepted_research": False,
        "execution_authorized": False,
    }
    _json(out / "receipt.json", state)
    began = time.monotonic()
    series = {}
    try:
        for metric in METHODS:
            if state["attempts"]:
                (sleep or time.sleep)(2)
            remaining = max_seconds - (time.monotonic() - began)
            if (
                remaining <= 0
                or state["attempts"] >= max_requests
                or state["estimated_cu"] + 150 > max_cu
            ):
                raise ValueError("NODIT_BUDGET_EXHAUSTED")
            state.update(status="acquiring", in_flight=True, spend_uncertain=True)
            state["attempts"] += 1
            state["estimated_cu"] += 150
            _json(out / "receipt.json", state)
            body = transport.fetch(
                metric, start, end, timeout=min(30, remaining), max_bytes=MAX_BYTES
            )
            if not isinstance(body, bytes) or len(body) > MAX_BYTES:
                raise ValueError("NODIT_RESPONSE_TOO_LARGE")
            state.update(in_flight=False, spend_uncertain=False)
            state["observations"].append(
                {
                    "metric": metric,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            _bytes(out / "raw" / (metric + ".json"), body)
            _json(out / "receipt.json", state)
            series[metric] = _series(body, dates)
        if time.monotonic() - began >= max_seconds:
            raise ValueError("NODIT_BUDGET_EXHAUSTED")
        _bytes(out / "normalized.csv", _csv(dates, series))
        state.update(
            status="acquired", completed_at=datetime.now(timezone.utc).isoformat()
        )
        _json(out / "receipt.json", state)
        records = [
            {
                "path": name,
                "bytes": (out / name).stat().st_size,
                "sha256": hashlib.sha256((out / name).read_bytes()).hexdigest(),
            }
            for name in sorted(FILES)
        ]
        _json(
            out / "manifest.json",
            {
                "schema": SCHEMA,
                "files": records,
                "accepted_research": False,
                "execution_authorized": False,
            },
        )
    except (OSError, ValueError, TimeoutError) as error:
        code = str(error)
        if not re.fullmatch(r"NODIT_[A-Z_0-9]+", code):
            code = "NODIT_ACQUISITION_BLOCKED"
        state.update(status="blocked", issue_code=code)
        _json(out / "receipt.json", state)
    return state


def verify(output):
    out = safe_path(Path(output))
    manifest_path = safe_path(out / "manifest.json")
    if manifest_path.stat().st_size > 65536:
        raise ValueError("NODIT_MANIFEST_INVALID")
    manifest = decode_json(manifest_path.read_bytes())
    if (
        not isinstance(manifest, dict)
        or set(manifest)
        != {"schema", "files", "accepted_research", "execution_authorized"}
        or manifest["schema"] != SCHEMA
        or manifest["accepted_research"] is not False
        or manifest["execution_authorized"] is not False
        or not isinstance(manifest["files"], list)
    ):
        raise ValueError("NODIT_MANIFEST_INVALID")
    entries = list(out.rglob("*"))
    for entry in entries:
        safe_path(entry)
        if not entry.is_file() and (not entry.is_dir() or entry != out / "raw"):
            raise ValueError("NODIT_INVENTORY_INVALID")
    actual = {p.relative_to(out).as_posix() for p in entries if p.is_file()}
    if actual != FILES | {"manifest.json"} or len(manifest["files"]) != len(FILES):
        raise ValueError("NODIT_INVENTORY_INVALID")
    seen = set()
    for record in manifest["files"]:
        if (
            not isinstance(record, dict)
            or set(record) != {"path", "bytes", "sha256"}
            or not isinstance(record["path"], str)
            or record["path"] not in FILES
            or record["path"] in seen
        ):
            raise ValueError("NODIT_INVENTORY_INVALID")
        seen.add(record["path"])
        file = safe_path(out / record["path"])
        if file.stat().st_size > MAX_BYTES or type(record["bytes"]) is not int:
            raise ValueError("NODIT_PAYLOAD_INVALID")
        body = file.read_bytes()
        if (
            len(body) != record["bytes"]
            or hashlib.sha256(body).hexdigest() != record["sha256"]
        ):
            raise ValueError("NODIT_HASH_MISMATCH")
    plan = decode_json((out / "plan.json").read_bytes())
    state = decode_json((out / "receipt.json").read_bytes())
    try:
        if set(plan) != {
            "schema",
            "chain",
            "network",
            "start",
            "end",
            "created_at",
            "metrics",
            "budget",
            "estimated_cu_per_request",
            "publication_delay_minutes",
            "accepted_research",
            "execution_authorized",
        }:
            raise ValueError
        if set(state) != {
            "schema",
            "status",
            "attempts",
            "estimated_cu",
            "spend_uncertain",
            "in_flight",
            "issue_code",
            "observations",
            "accepted_research",
            "execution_authorized",
            "completed_at",
        }:
            raise ValueError
        created = _timestamp(plan["created_at"])
        dates = _window(plan["start"], plan["end"], created)
        b = plan["budget"]
        if set(b) != {"max_requests", "max_cu", "max_seconds", "max_response_bytes"}:
            raise ValueError
        _budgets(b["max_requests"], b["max_cu"], b["max_seconds"])
        if (
            not isinstance(state["observations"], list)
            or len(state["observations"]) != 2
        ):
            raise ValueError
        observed_times = []
        for record in state["observations"]:
            if not isinstance(record, dict) or set(record) != {"metric", "observed_at"}:
                raise ValueError
            observed_times.append(_timestamp(record["observed_at"]))
        completed = _timestamp(state["completed_at"])
        if (
            not created
            <= observed_times[0]
            <= observed_times[1]
            <= completed
            <= datetime.now(timezone.utc)
        ):
            raise ValueError
        if (
            plan["schema"] != SCHEMA
            or plan["chain"] != "ethereum"
            or plan["network"] != "mainnet"
            or plan["metrics"] != list(METHODS)
            or plan["estimated_cu_per_request"] != 150
            or plan["publication_delay_minutes"] != 30
            or b["max_response_bytes"] != MAX_BYTES
            or state["schema"] != SCHEMA
            or state["status"] != "acquired"
            or type(state["attempts"]) is not int
            or state["attempts"] != 2
            or type(state["estimated_cu"]) is not int
            or state["estimated_cu"] != 300
            or state["in_flight"] is not False
            or state["spend_uncertain"] is not False
            or state["issue_code"] is not None
            or [x["metric"] for x in state["observations"]] != list(METHODS)
            or any(
                obj[k] is not False
                for obj in (state, plan)
                for k in ("accepted_research", "execution_authorized")
            )
        ):
            raise ValueError
        series = {
            m: _series((out / "raw" / (m + ".json")).read_bytes(), dates)
            for m in METHODS
        }
        if (out / "normalized.csv").read_bytes() != _csv(dates, series):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("NODIT_BUNDLE_INVALID") from None
    return {
        "status": "acquired",
        "start": plan["start"],
        "end": plan["end"],
        "rows": len(dates),
        "attempts": 2,
        "estimated_cu": 300,
        "accepted_research": False,
        "execution_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    acquire = commands.add_parser("collect", help="Manually collect two daily series")
    acquire.add_argument("--credential-file", type=Path, required=True)
    acquire.add_argument("--start", required=True)
    acquire.add_argument("--end", required=True)
    acquire.add_argument("--output", type=Path, required=True)
    acquire.add_argument("--max-requests", type=int, default=4)
    acquire.add_argument("--max-cu", type=int, default=600)
    acquire.add_argument("--max-seconds", type=int, default=120)
    inspect = commands.add_parser(
        "verify", help="Verify a retained bundle without network access"
    )
    inspect.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "collect":
            from .nodit_transport import NoditTransport

            result = collect(
                args.start,
                args.end,
                args.output,
                transport=NoditTransport(args.credential_file),
                max_requests=args.max_requests,
                max_cu=args.max_cu,
                max_seconds=args.max_seconds,
            )
        else:
            result = verify(args.output)
    except (OSError, ValueError, TypeError):
        result = {"status": "blocked", "issue_code": "NODIT_INPUT_OR_BUNDLE_INVALID"}
    print(json.dumps(result, allow_nan=False))
    return 0 if result["status"] == "acquired" else 1


if __name__ == "__main__":
    raise SystemExit(main())
