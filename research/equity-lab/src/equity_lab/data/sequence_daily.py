"""Read-only adapter for hash-bound daily snapshots; no research promotion."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def strict_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("NONFINITE_JSON")

    return json.loads(
        Path(path).read_text(), object_pairs_hook=pairs, parse_constant=invalid
    )


def session_schedule(start, end):
    import exchange_calendars as calendars

    calendar = calendars.get_calendar("XNYS", start=start, end=end)
    schedule = calendar.schedule.loc[start:end, ["open", "close"]].copy()
    schedule.index = schedule.index.strftime("%Y-%m-%d")
    return schedule


def validate_frame(frame, schedule):
    required = ["date", "open", "high", "low", "close", "volume"]
    if not set(required) <= set(frame):
        raise ValueError("MISSING_DAILY_FIELDS")
    if frame.date.tolist() != schedule.index.tolist():
        raise ValueError("INVALID_SESSION_GRID")
    values = frame[required[1:]].to_numpy(dtype=float)
    if (
        not np.isfinite(values).all()
        or (values[:, :4] <= 0).any()
        or (values[:, 4] < 0).any()
    ):
        raise ValueError("INVALID_DAILY_VALUES")
    if (
        (frame.high < frame[["open", "close", "low"]].max(axis=1))
        | (frame.low > frame[["open", "close", "high"]].min(axis=1))
    ).any():
        raise ValueError("INVALID_OHLC_BOUNDS")
    return frame[required].set_index("date")


@dataclass
class DailySnapshot:
    root: Path
    manifest: dict
    frames: dict
    schedule: pd.DataFrame
    bindings: dict

    def verify(self):
        for name, binding in self.bindings.items():
            path = self.root / name
            if (
                path.is_symlink()
                or not path.is_file()
                or path.stat().st_size != binding["bytes"]
                or digest(path) != binding["sha256"]
            ):
                raise ValueError("INPUT_INTEGRITY_FAILED")


def load_daily_snapshot(manifest_path, expected_sha256):
    path = Path(manifest_path).absolute()
    if path.is_symlink() or digest(path) != expected_sha256:
        raise ValueError("MANIFEST_INTEGRITY_FAILED")
    root = path.parent.resolve()
    manifest = strict_json(path)
    spec = manifest["spec"]
    expected = dict(
        source="ibkr_daily",
        market="US",
        calendar="XNYS",
        timezone="America/New_York",
        price_basis="split_adjusted",
        universe_status="fixed_current",
        quote_currency="USD",
    )
    if (
        manifest.get("schema") != "competition.dataset_manifest.v2"
        or any(spec.get(k) != v for k, v in expected.items())
        or manifest.get("status") != "acquired"
        or manifest.get("accepted_research") is not False
    ):
        raise ValueError("UNSUPPORTED_SNAPSHOT")
    receipt = strict_json(root / "receipt.json")
    if (
        receipt != manifest["receipt"]
        or receipt.get("status") != "acquired"
        or receipt.get("spec_hash") != manifest["spec_hash"]
        or receipt.get("gaps")
    ):
        raise ValueError("RECEIPT_MISMATCH")
    bindings = {}
    for item in manifest["files"]:
        name = item["path"]
        relative = Path(name)
        target = root / relative
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or name in bindings
            or any(
                (root / Path(*relative.parts[:i])).is_symlink()
                for i in range(1, len(relative.parts) + 1)
            )
            or not target.resolve().is_relative_to(root)
        ):
            raise ValueError("UNSAFE_INPUT_PATH")
        bindings[name] = dict(bytes=item["bytes"], sha256=item["sha256"])
    for file in [path, root / "receipt.json"]:
        bindings[file.name] = dict(bytes=file.stat().st_size, sha256=digest(file))
    snapshot = DailySnapshot(root, manifest, {}, pd.DataFrame(), bindings)
    snapshot.verify()
    schedule = session_schedule(spec["start"], spec["end"])
    symbols = [*spec["products"], spec["benchmark"]]
    if len(set(symbols)) != len(symbols) or any(
        not isinstance(n, str) or not n.isalnum() for n in symbols
    ):
        raise ValueError("INVALID_SYMBOLS")
    for symbol in symbols:
        name = f"normalized/{symbol}.csv"
        if name not in bindings:
            raise ValueError("UNBOUND_NORMALIZED_INPUT")
        snapshot.frames[symbol] = validate_frame(pd.read_csv(root / name), schedule)
    snapshot.schedule = schedule
    snapshot.verify()
    return snapshot
