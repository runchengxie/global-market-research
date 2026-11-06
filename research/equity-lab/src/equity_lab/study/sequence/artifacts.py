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


def source_identity():
    import subprocess

    package = Path(__file__).resolve().parents[2]
    files = {
        str(p.relative_to(package)): digest(p) for p in sorted(package.rglob("*.py"))
    }
    try:
        revision = subprocess.check_output(
            ["git", "-C", str(package), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty = subprocess.check_output(
            ["git", "-C", str(package), "status", "--porcelain"], text=True
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        revision, dirty = None, None
    return dict(revision=revision, dirty=dirty, files=files)


def local_report(summary):
    from html import escape

    sections = []
    for row in summary["completed"]:
        counts = row["classification"]["confusion"]
        title = escape(f"{row['model']} / fold {row['fold']} / seed {row['seed']}")
        cells = "".join(
            '<tr><th scope="row">'
            + label
            + "</th>"
            + "".join(f"<td>{n}</td>" for n in values)
            + "</tr>"
            for label, values in zip(["Not above", "Above"], counts)
        )
        sections.append(
            f'<section><h2>{title}</h2><table><caption>Confusion matrix: actual rows, predicted columns</caption><thead><tr><th></th><th scope="col">Not above</th><th scope="col">Above</th></tr></thead><tbody>{cells}</tbody></table></section>'
        )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Private exploratory sequence report</title><h1>Private exploratory sequence report</h1><p>Status: '
        + escape(summary["status"])
        + "</p><p>Retrospective, fixed-current, split-adjusted price simulation; no dividends or research promotion.</p>"
        + "".join(sections)
        + "</html>"
    )
