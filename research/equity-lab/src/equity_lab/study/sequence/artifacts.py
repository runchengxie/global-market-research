"""Exclusive local bundles with content digests; never public projections."""

import json
from pathlib import Path
from equity_lab.data.sequence_daily import digest, strict_json


def write_json(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, allow_nan=False, default=str) + "\n"
    )


def create_bundle(path, config):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    write_json(path / "config.json", config)


def seal_bundle(path):
    path = Path(path)
    inventory = {
        str(p.relative_to(path)): digest(p)
        for p in sorted(path.rglob("*"))
        if p.is_file() and p.name != "checksums.json"
    }
    write_json(path / "checksums.json", inventory)


def verify_bundle(path):
    path = Path(path)
    inventory = strict_json(path / "checksums.json")
    actual = {
        str(p.relative_to(path))
        for p in path.rglob("*")
        if p.is_file() and p.name != "checksums.json"
    }
    if actual != set(inventory):
        raise ValueError("BUNDLE_INTEGRITY_FAILED")
    for name, expected in inventory.items():
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or (path / relative).is_symlink()
            or digest(path / relative) != expected
        ):
            raise ValueError("BUNDLE_INTEGRITY_FAILED")
    return dict(files=len(inventory), status="verified")
