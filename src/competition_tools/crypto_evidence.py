"""External immutable crypto evidence, never a strategy execution handoff."""

import hashlib
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from competition_tools.datasets.daily_storage import safe_path
from competition_tools.datasets.storage import write_json


def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def read_json(path):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError("DUPLICATE_JSON_KEY")
            out[k] = v
        return out

    def invalid(value):
        raise ValueError("NONFINITE_JSON")

    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=invalid,
    )


def new_output(path, *, inputs=()):
    path = safe_path(Path(path))
    if any((p / "seal.json").exists() for p in path.parents):
        raise ValueError("OUTPUT_INSIDE_SEALED_EVIDENCE")
    for source in inputs:
        source = safe_path(Path(source))
        if path.is_relative_to(source) or source.is_relative_to(path):
            raise ValueError("OUTPUT_OVERLAPS_EVIDENCE")
    path.mkdir(parents=True, exist_ok=False)
    return path


def file_records(root):
    root = safe_path(Path(root))
    out = []
    for p in sorted(root.rglob("*")):
        safe_path(p)
        if p.is_file() and p != root / "seal.json":
            out.append(
                dict(
                    path=p.relative_to(root).as_posix(),
                    sha256=digest(p),
                    bytes=p.stat().st_size,
                )
            )
    return out


def seal(root):
    root = safe_path(Path(root))
    if (root / "seal.json").exists():
        raise FileExistsError("ALREADY_SEALED")
    value = dict(schema="crypto.evidence_seal.v1", files=file_records(root))
    write_json(root / "seal.json", value)
    return value


def verify_seal(root):
    root = safe_path(Path(root))
    value = read_json(root / "seal.json")
    if (
        set(value) != {"schema", "files"}
        or value["schema"] != "crypto.evidence_seal.v1"
        or value["files"] != file_records(root)
    ):
        raise ValueError("EVIDENCE_SEAL_MISMATCH")
    return value


def claim_plan(plan_file, purpose):
    path = safe_path(Path(plan_file))
    plan = read_json(path)
    claim = safe_path(Path(plan["claim_file"]))
    if claim != path.parent.with_name(path.parent.name + "." + purpose + "-claim"):
        raise ValueError("INVALID_PLAN_CLAIM")
    body = json.dumps(
        dict(
            plan_sha256=digest(path),
            purpose=purpose,
            pid=os.getpid(),
            claimed_at=datetime.now(timezone.utc).isoformat(),
        )
    )
    with claim.open("x", encoding="utf-8") as f:
        os.chmod(claim, 0o600)
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    return plan


def bounded_worker(command, *, timeout, max_bytes):
    if timeout <= 0 or max_bytes <= 0:
        raise ValueError("INVALID_WORKER_BUDGET")
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    try:
        output, _ = process.communicate(timeout=timeout)
    except BaseException as exc:
        process.kill()
        process.communicate()
        if isinstance(exc, subprocess.TimeoutExpired):
            raise TimeoutError("CRYPTO_TRANSFER_DEADLINE") from exc
        raise
    if process.returncode or len(output) < 4 or len(output) > max_bytes + 4:
        raise ValueError("UNKNOWN_CRYPTO_TRANSFER_SPEND")
    return int.from_bytes(output[:4], "big"), output[4:]
