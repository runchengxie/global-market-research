"""Bounded public hourly archives and derived UTC four-hour bars."""

import calendar
import csv
import hashlib
import io
import math
import stat
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from competition_tools.crypto_evidence import (
    new_output,
    read_json,
    seal,
    verify_seal,
    digest,
    claim_plan,
)
from .storage import write_json

PRODUCTS = ["BTCUSDT", "ETHUSDT"]
MONTHS = [
    f"{y}-{m:02d}"
    for y in (2024, 2025, 2026)
    for m in range(1, 13)
    if "2024-10" <= f"{y}-{m:02d}" <= "2026-09"
]
BUDGET = dict(
    attempts=112,
    transferred_bytes=32 * 1024**2,
    expanded_bytes=64 * 1024**2,
    per_zip_bytes=8 * 1024**2,
    seconds=600,
)
FIELDS = [
    "asset",
    "time_open",
    "interval_end",
    "open",
    "high",
    "low",
    "close",
    "volume",
]


def archive_url(product, month):
    if product not in PRODUCTS or month not in MONTHS:
        raise ValueError("UNAPPROVED_INTRADAY_ARCHIVE")
    return f"https://data.binance.vision/data/spot/monthly/klines/{product}/1h/{product}-1h-{month}.zip"


def stamp(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_hourly(payload, checksum, product, month):
    archive_url(product, month)
    name = f"{product}-1h-{month}"
    fields = checksum.strip().split()
    if (
        len(fields) != 2
        or fields[1].lstrip("*") != name + ".zip"
        or fields[0] != hashlib.sha256(payload).hexdigest()
    ):
        raise ValueError("ARCHIVE_CHECKSUM")
    if len(payload) > BUDGET["per_zip_bytes"]:
        raise ValueError("ARCHIVE_SIZE")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            members = z.infolist()
            if len(members) != 1 or members[0].filename != name + ".csv":
                raise ValueError("ARCHIVE_MEMBER")
            m = members[0]
            if (
                m.flag_bits & 1
                or stat.S_ISLNK(m.external_attr >> 16)
                or m.file_size > BUDGET["per_zip_bytes"]
            ):
                raise ValueError("UNSAFE_ZIP")
            with z.open(m) as f:
                body = f.read(BUDGET["per_zip_bytes"] + 1)
            if len(body) > BUDGET["per_zip_bytes"]:
                raise ValueError("EXPANDED_SIZE")
    except (zipfile.BadZipFile, RuntimeError, UnicodeError) as exc:
        raise ValueError("INVALID_ZIP") from exc
    start = datetime.fromisoformat(month + "-01T00:00:00+00:00")
    count = calendar.monthrange(start.year, start.month)[1] * 24
    divisor = 1000000 if month >= "2025-01" else 1000
    rows = []
    for i, r in enumerate(csv.reader(io.StringIO(body.decode("utf-8-sig")))):
        if len(r) != 12:
            raise ValueError("KLINE_COLUMNS")
        expected = start + timedelta(hours=i)
        opening = int(expected.timestamp()) * divisor
        if (
            i >= count
            or int(r[0]) != opening
            or int(r[6]) != opening + 3600 * divisor - 1
        ):
            raise ValueError("KLINE_GRID_OR_UNIT")
        values = list(map(float, r[1:6]))
        opening_price, high, low, close, volume = values
        if (
            not all(math.isfinite(x) for x in values)
            or min(opening_price, high, low, close) <= 0
            or volume < 0
            or not low <= min(opening_price, close) <= max(opening_price, close) <= high
        ):
            raise ValueError("INVALID_OHLCV")
        rows.append(
            dict(
                zip(
                    FIELDS,
                    [
                        product,
                        stamp(expected),
                        stamp(expected + timedelta(hours=1)),
                        *values,
                    ],
                    strict=True,
                )
            )
        )
    if len(rows) != count:
        raise ValueError("MISSING_HOURLY_BARS")
    return rows


def aggregate_four(rows):
    result = []
    if len(rows) % 4:
        raise ValueError("INCOMPLETE_FOUR_HOUR_GROUP")
    for i in range(0, len(rows), 4):
        group = rows[i : i + 4]
        start = datetime.fromisoformat(group[0]["time_open"].replace("Z", "+00:00"))
        if start.hour % 4 or any(
            r["asset"] != group[0]["asset"]
            or r["time_open"] != stamp(start + timedelta(hours=j))
            or r["interval_end"] != stamp(start + timedelta(hours=j + 1))
            for j, r in enumerate(group)
        ):
            raise ValueError("FOUR_HOUR_GRID")
        result.append(
            dict(
                asset=group[0]["asset"],
                time_open=group[0]["time_open"],
                interval_end=group[-1]["interval_end"],
                open=group[0]["open"],
                high=max(r["high"] for r in group),
                low=min(r["low"] for r in group),
                close=group[-1]["close"],
                volume=sum(r["volume"] for r in group),
            )
        )
    return result


def freeze_intraday_plan(output, *, now):
    if now.tzinfo is None or now < datetime(2026, 10, 2, tzinfo=timezone.utc):
        raise ValueError("INVALID_FREEZE_CLOCK")
    output = new_output(output)
    value = dict(
        schema="crypto.hourly_plan.v1",
        frozen_at=now.isoformat(),
        products=PRODUCTS,
        months=MONTHS,
        budget=BUDGET,
        claim_file=str(output.with_name(output.name + ".acquire-claim")),
        resources=[
            dict(product=p, month=m, url=archive_url(p, m) + suffix)
            for p in PRODUCTS
            for m in MONTHS
            for suffix in ("", ".CHECKSUM")
        ],
        accepted_research=False,
    )
    write_json(output / "plan.json", value)
    return value


def acquire_intraday(plan_file, output, transport):
    plan_digest = digest(plan_file)
    plan = read_json(plan_file)
    expected = [
        dict(product=p, month=m, url=archive_url(p, m) + s)
        for p in PRODUCTS
        for m in MONTHS
        for s in ("", ".CHECKSUM")
    ]
    if (
        plan["schema"] != "crypto.hourly_plan.v1"
        or plan["resources"] != expected
        or plan["budget"] != BUDGET
    ):
        raise ValueError("INVALID_INTRADAY_PLAN")
    output = Path(output)
    # Check containment before either acquiring a claim or touching output.
    from .daily_storage import safe_path

    target = safe_path(output)
    parent = safe_path(Path(plan_file).parent)
    if target.is_relative_to(parent) or parent.is_relative_to(target):
        raise ValueError("OUTPUT_OVERLAPS_PLAN")
    if target.exists():
        raise FileExistsError("OUTPUT_EXISTS")
    if claim_plan(plan_file, "acquire") != plan or digest(plan_file) != plan_digest:
        raise ValueError("PLAN_CHANGED")
    output = new_output(output, inputs=[parent])
    (output / "raw").mkdir()
    (output / "normalized").mkdir()
    start = time.monotonic()
    ledger = dict(
        status="running",
        attempts=0,
        transferred_bytes=0,
        expanded_bytes=0,
        unknown_spend=False,
        completed_resources=0,
    )
    write_json(output / "plan.json", plan)
    all_rows = {p: [] for p in PRODUCTS}
    payloads = {}
    expanded = 0
    try:
        for resource in expected:
            for retry in range(3):
                remaining = BUDGET["seconds"] - (time.monotonic() - start)
                if ledger["attempts"] >= BUDGET["attempts"] or remaining <= 0:
                    raise TimeoutError("ACQUISITION_BUDGET")
                limit = min(
                    BUDGET["per_zip_bytes"]
                    if resource["url"].endswith(".zip")
                    else 1024,
                    BUDGET["transferred_bytes"] - ledger["transferred_bytes"],
                )
                if limit <= 0:
                    raise ValueError("TRANSFER_BUDGET")
                ledger["attempts"] += 1
                ledger["unknown_spend"] = True
                write_json(output / "ledger.json", ledger)
                code, body = transport.fetch(
                    resource["url"], max_bytes=limit, timeout=min(30, remaining)
                )
                ledger["transferred_bytes"] += len(body)
                ledger["unknown_spend"] = False
                write_json(output / "ledger.json", ledger)
                if code in (429, 500, 502, 503, 504) and retry < 2:
                    time.sleep(
                        min(
                            2**retry,
                            max(0, BUDGET["seconds"] - (time.monotonic() - start)),
                        )
                    )
                    continue
                if code != 200:
                    raise ValueError(f"ARCHIVE_HTTP_{code}")
                break
            filename = resource["url"].rsplit("/", 1)[-1]
            (output / "raw" / filename).write_bytes(body)
            ledger["completed_resources"] += 1
            p, m = resource["product"], resource["month"]
            key = (p, m)
            if resource["url"].endswith(".zip"):
                payloads[key] = body
            else:
                payload = payloads.pop(key)
                with zipfile.ZipFile(io.BytesIO(payload)) as z:
                    expanded += sum(x.file_size for x in z.infolist())
                if expanded > BUDGET["expanded_bytes"]:
                    raise ValueError("EXPANSION_BUDGET")
                all_rows[p].extend(
                    normalize_hourly(payload, body.decode("ascii"), p, m)
                )
                ledger["expanded_bytes"] = expanded
        for p, rows in all_rows.items():
            for interval, values in [("1h", rows), ("4h", aggregate_four(rows))]:
                with (output / "normalized" / f"{p}-{interval}.csv").open(
                    "w", newline=""
                ) as f:
                    w = csv.DictWriter(f, fieldnames=FIELDS)
                    w.writeheader()
                    w.writerows(values)
        if digest(plan_file) != plan_digest:
            raise ValueError("PLAN_CHANGED")
        ledger.update(status="completed", elapsed_seconds=time.monotonic() - start)
    except (Exception, KeyboardInterrupt) as exc:
        ledger.update(
            status="partial",
            reason=type(exc).__name__ + ":" + str(exc),
            elapsed_seconds=time.monotonic() - start,
        )
    write_json(output / "ledger.json", ledger)
    manifest = dict(
        schema="crypto.hourly_manifest.v1",
        status=ledger["status"],
        source="binance_spot",
        products=PRODUCTS,
        quote_currency="USDT",
        price_basis="raw",
        timezone="UTC",
        start="2024-10-01T00:00:00Z",
        end_exclusive="2026-10-01T00:00:00Z",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        plan_sha256=plan_digest,
        budget=ledger,
        coverage={
            p: {"1h": len(rows), "4h": len(rows) // 4} for p, rows in all_rows.items()
        },
        timestamp_units={"before_2025": "milliseconds", "from_2025": "microseconds"},
        historical_availability="unverified_bar_close_proxy",
        accepted_research=False,
    )
    write_json(output / "manifest.json", manifest)
    seal(output)
    return manifest


def verify_intraday(path):
    path = Path(path)
    verify_seal(path)
    m = read_json(path / "manifest.json")
    if (
        m["schema"] != "crypto.hourly_manifest.v1"
        or m["status"] != "completed"
        or m["accepted_research"] is not False
        or m["products"] != PRODUCTS
    ):
        raise ValueError("INCOMPLETE_HOURLY_INPUT")
    return m
