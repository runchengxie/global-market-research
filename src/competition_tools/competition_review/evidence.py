"""Offline source inventory; calendar scenarios never certify official session labels."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib
import json
from importlib.metadata import version
from competition_tools.crypto_evidence import read_json, digest
from competition_tools.datasets.daily_storage import safe_path
from .participation import decimal

START = datetime(2026, 10, 25, 16, tzinfo=timezone.utc)
END = datetime(2027, 1, 26, 22, tzinfo=timezone.utc)
HKT = timezone(timedelta(hours=8))


def aware(value):
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError("AWARE_TIME_REQUIRED")
    return t.astimezone(timezone.utc)


def load_observations(root, as_of):
    root = safe_path(Path(root))
    as_of = aware(as_of.isoformat())
    files = sorted(
        set(root.glob("*/snapshot.json"))
        | set(root.glob("daily-history/history/*/*/snapshot.json"))
    )
    if len(files) > 2048:
        raise ValueError("SNAPSHOT_INVENTORY_LIMIT")
    observations = {}
    conflicts = set()
    invalid = []
    sources = []
    duplicates = 0
    for p in files:
        relative = p.relative_to(root).as_posix()
        try:
            safe_path(p)
            raw = read_json(p)
            t = aware(raw["observed_at"])
            if t > as_of:
                raise ValueError("FUTURE_OBSERVATION")
            nav = decimal(raw["net_liquidation_sgd"])
            gross = decimal(raw["gross_position_sgd"])
            if nav <= 0:
                raise ValueError("INVALID_NAV")
            positions = []
            for r in raw["stock_positions"]:
                qty = signed_decimal(r["quantity"])
                positions.append(
                    dict(
                        symbol=str(r["symbol"]),
                        quantity=str(qty),
                        currency=str(r["currency"]),
                    )
                )
            canonical = hashlib.sha256(
                json.dumps(
                    raw, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
            ).hexdigest()
            key = t.isoformat()
            sources.append(dict(path=relative, sha256=digest(p)))
            if key in conflicts:
                continue
            if key in observations:
                if observations[key]["canonical_sha256"] == canonical:
                    duplicates += 1
                else:
                    conflicts.add(key)
                    del observations[key]
                continue
            observations[key] = dict(
                observed_at=key,
                hkt_observation_date=t.astimezone(HKT).date().isoformat(),
                base_currency="SGD",
                nav=str(nav),
                gross_value=str(gross),
                gross_position_proxy=str(gross / nav),
                stock_positions=positions,
                canonical_sha256=canonical,
                source=relative,
                official_session_label=None,
                official_day_complete=False,
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            invalid.append(
                dict(path=relative, reason=type(exc).__name__ + ":" + str(exc)[:120])
            )
    return dict(
        observations=sorted(observations.values(), key=lambda r: r["observed_at"]),
        duplicate_files=duplicates,
        conflicts=sorted(conflicts),
        invalid_files=invalid,
        sources=sources,
    )


def signed_decimal(value):
    from decimal import Decimal, InvalidOperation

    if type(value) not in [str, int, float, Decimal]:
        raise ValueError("INVALID_QUANTITY")
    try:
        q = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("INVALID_QUANTITY") from exc
    if not q.is_finite():
        raise ValueError("INVALID_QUANTITY")
    return q


def calendar_scenario(name, as_of):
    if name not in ["XNYS", "XTKS"]:
        raise ValueError("UNSUPPORTED_CALENDAR_SCENARIO")
    as_of = aware(as_of.isoformat())
    try:
        import exchange_calendars as xc
    except ImportError:
        raise ValueError("DAILY_DATA_PROFILE_REQUIRED") from None
    schedule = xc.get_calendar(name, start="2026-10-25", end="2027-01-28").schedule
    records = [
        dict(
            session_date=t.date().isoformat(),
            open=r["open"].isoformat(),
            close=r["close"].isoformat(),
        )
        for t, r in schedule.iterrows()
        if aware(r["open"].isoformat()) >= START and aware(r["close"].isoformat()) < END
    ]
    return dict(
        calendar=name,
        status="unconfirmed_scenario",
        package_version=version("exchange-calendars"),
        schedule_sha256=hashlib.sha256(
            json.dumps(records, sort_keys=True).encode()
        ).hexdigest(),
        period_start=START.isoformat(),
        period_end_exclusive=END.isoformat(),
        all_sessions=[r["session_date"] for r in records],
        elapsed_sessions=[
            r["session_date"] for r in records if aware(r["close"]) <= as_of
        ],
        remaining_sessions=[
            r["session_date"] for r in records if aware(r["close"]) > as_of
        ],
    )
