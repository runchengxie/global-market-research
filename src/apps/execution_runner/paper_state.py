"""Durable run claims and account uncertainty across project-root aliases."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path

from competition_tools.project_storage import (
    CANONICAL,
    LEGACY,
    alternate_locations,
    guarded_location,
)
from packages.audit import EventJournal
from packages.execution_policies.paper_allocation import AllocationError


def durable_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if os.name != "nt":
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


class AllocationState:
    def __init__(self, root, spec):
        self.root, self.spec = Path(root), spec
        # Validates path and source/symlink exclusion before creating anything.
        alternate_locations(self.root, "validation")
        key = hashlib.sha256(spec.account.encode()).hexdigest()
        self.account_relative = f"accounts/{key}"
        self.run_relative = f"runs/{spec.run_id}"
        self.journal = EventJournal(self.root / self.run_relative / "events.jsonl")
        self.fingerprint = hashlib.sha256(
            json.dumps(spec.to_dict(), sort_keys=True).encode()
        ).hexdigest()

    @contextmanager
    def account_lock(self):
        # OS locks release on process death; durable uncertainty is a separate file.
        project = next(
            (
                p
                for p in (self.root, *self.root.parents)
                if p.name in (CANONICAL, LEGACY)
            ),
            None,
        )
        namespace = (
            CANONICAL + ":" + self.root.relative_to(project).as_posix()
            if project
            else str(self.root)
        )
        token = hashlib.sha256(
            (namespace + ":" + self.account_relative).encode()
        ).hexdigest()
        locks = (
            project.parent if project else self.root.parent
        ) / ".global-market-research-guards"
        alternate_locations(locks, "validation")
        locks.mkdir(parents=True, exist_ok=True)
        fd = os.open(locks / (token + ".account-lock"), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.name == "nt":
                import msvcrt

                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def unresolved(self):
        return [
            p
            for p in alternate_locations(
                self.root, self.account_relative + "/unresolved.json"
            )
            if p.exists()
        ]

    def claim(self):
        if self.unresolved():
            raise AllocationError("account_requires_reconciliation")
        with guarded_location(self.root, self.run_relative + "/claim.json") as path:
            durable_json(path, {"spec_sha256": self.fingerprint})

    def assert_claim(self):
        path = self.root / self.run_relative / "claim.json"
        if json.loads(path.read_text()) != {"spec_sha256": self.fingerprint}:
            raise AllocationError("reconciliation_spec_mismatch")
        for marker in self.unresolved():
            if json.loads(marker.read_text()).get("run_id") != self.spec.run_id:
                raise AllocationError("different_run_requires_reconciliation")

    def mark_unresolved(self):
        if not self.unresolved():
            durable_json(
                self.root / self.account_relative / "unresolved.json",
                {"run_id": self.spec.run_id},
            )

    def clear_unresolved(self):
        self.assert_claim()
        for path in self.unresolved():
            path.unlink()

    def record(self, event_id, kind, **value):
        event = {
            "event_id": event_id,
            "kind": kind,
            "run_id": self.spec.run_id,
            **value,
        }
        existing = next(
            (e for e in self.journal.read() if e["event_id"] == event_id), None
        )
        if existing is not None and existing != event:
            raise AllocationError("conflicting_broker_evidence")
        self.journal.append(event)
