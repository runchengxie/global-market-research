"""Independent file contracts for verified hourly prices and factor snapshots."""

import csv
import hashlib
import json
import math
from pathlib import Path
from datetime import datetime, timedelta

PRODUCTS = ["BTCUSDT", "ETHUSDT"]
INDICATORS = ["CO-A-02-03", "CO-S-01-01", "CO-S-01-05"]


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def read(path):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError("DUPLICATE_JSON_KEY")
            out[k] = v
        return out

    def invalid(v):
        raise ValueError("NONFINITE_JSON")

    return json.loads(
        Path(path).read_text(), object_pairs_hook=pairs, parse_constant=invalid
    )


def external(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("ABSOLUTE_EXTERNAL_PATH_REQUIRED")
    for p in [path, *path.parents]:
        if (
            p.is_symlink()
            or (hasattr(p, "is_junction") and p.is_junction())
            or (p / ".git").exists()
        ):
            raise ValueError("UNSAFE_EXTERNAL_PATH")
    return path.resolve()


def records(root):
    root = external(root)
    out = []
    for p in sorted(root.rglob("*")):
        external(p)
        if p.is_file() and p != root / "seal.json":
            out.append(
                dict(
                    path=p.relative_to(root).as_posix(),
                    sha256=sha(p),
                    bytes=p.stat().st_size,
                )
            )
    return out


def verify(root):
    root = external(root)
    seal = read(root / "seal.json")
    if seal != {"schema": "crypto.evidence_seal.v1", "files": records(root)}:
        raise ValueError("EVIDENCE_SEAL_MISMATCH")
    return seal


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def seal(root):
    write(
        Path(root) / "seal.json",
        dict(schema="crypto.evidence_seal.v1", files=records(root)),
    )


def instant(value):
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.utcoffset() != timedelta(0):
        raise ValueError("UTC_REQUIRED")
    return t


def load_prices(root):
    root = external(root)
    verify(root)
    m = read(root / "manifest.json")
    if (
        m.get("schema") != "crypto.hourly_manifest.v1"
        or m.get("status") != "completed"
        or m.get("accepted_research") is not False
        or m.get("quote_currency") != "USDT"
        or m.get("products") != PRODUCTS
    ):
        raise ValueError("INVALID_HOURLY_MANIFEST")
    out = {}
    for step in [1, 4]:
        out[step] = {}
        for p in PRODUCTS:
            with (root / "normalized" / f"{p}-{step}h.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            previous = None
            for r in rows:
                if (
                    set(r)
                    != {
                        "asset",
                        "time_open",
                        "interval_end",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                    }
                    or r["asset"] != p
                ):
                    raise ValueError("INVALID_PRICE_COLUMNS")
                t = instant(r["time_open"])
                end = instant(r["interval_end"])
                if end - t != timedelta(hours=step) or (previous and t != previous):
                    raise ValueError("INCOMPLETE_PRICE_GRID")
                previous = end
                for k in ["open", "high", "low", "close", "volume"]:
                    r[k] = float(r[k])
                if (
                    not all(
                        math.isfinite(r[k])
                        for k in ["open", "high", "low", "close", "volume"]
                    )
                    or min(r[k] for k in ["open", "high", "low", "close"]) <= 0
                    or r["volume"] < 0
                    or not r["low"]
                    <= min(r["open"], r["close"])
                    <= max(r["open"], r["close"])
                    <= r["high"]
                ):
                    raise ValueError("INVALID_PRICE_NUMBER")
            if (
                len(rows) != m["coverage"][p][f"{step}h"]
                or not rows
                or rows[0]["time_open"] != m["start"]
                or rows[-1]["interval_end"] != m["end_exclusive"]
            ):
                raise ValueError("PRICE_SCOPE_MISMATCH")
            out[step][p] = rows
    return m, out


def load_factors(path, expected_sha):
    path = external(path)
    if sha(path) != expected_sha:
        raise ValueError("FACTOR_SOURCE_CHANGED")
    raw = read(path)
    groups = {(p, i): [] for p in PRODUCTS for i in INDICATORS}
    seen = set()
    for r in raw:
        if set(r) != {
            "asset",
            "indicator",
            "period_start_utc",
            "period_end_utc",
            "value",
        }:
            raise ValueError("INVALID_FACTOR_COLUMNS")
        p = r["asset"] + "USDT"
        key = (p, r["indicator"])
        start, end = instant(r["period_start_utc"]), instant(r["period_end_utc"])
        if (
            key not in groups
            or end - start != timedelta(days=1)
            or start.hour
            or start.minute
            or start.second
            or (key, end) in seen
            or type(r["value"]) not in [int, float]
            or not math.isfinite(r["value"])
        ):
            raise ValueError("INVALID_FACTOR_RECORD")
        seen.add((key, end))
        groups[key].append(dict(period_end=end, value=float(r["value"])))
    for group in groups.values():
        group.sort(key=lambda r: r["period_end"])
        if not group or any(
            b["period_end"] - a["period_end"] != timedelta(days=1)
            for a, b in zip(group, group[1:])
        ):
            raise ValueError("FACTOR_DAILY_GAP")
    grids = [[x["period_end"] for x in g] for g in groups.values()]
    if any(g != grids[0] for g in grids):
        raise ValueError("FACTOR_SCOPE_MISMATCH")
    return groups, dict(
        rows=len(raw),
        assets=["BTC", "ETH"],
        indicators=INDICATORS,
        grain="1d",
        start=raw[0]["period_start_utc"],
        historical_publication=None,
        revision_policy=None,
        sha256=expected_sha,
    )
