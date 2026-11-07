"""Task-owned finite public-data observation process; no system scheduler changes."""

import argparse
import json
import os
import signal
import time
from datetime import timedelta
from pathlib import Path
from competition_tools.crypto_evidence import new_output, seal, digest
from competition_tools.datasets.storage import write_json
from .crypto_observation import (
    observation_history,
    capture_observation,
    RecentTransport,
    instant,
    utc,
)
from .crypto_monitor import monitor


def next_action(protocol, receipts, now):
    budget = protocol["budget"]
    if now >= instant(protocol["frozen_at"]) + timedelta(hours=48):
        return dict(action="stop", reason="48_hour_deadline")
    if (
        len(receipts) >= budget["captures"]
        or sum(r["http"]["attempts"] for r in receipts) + 2 > budget["http_attempts"]
        or sum(r["http"]["bytes"] for r in receipts) >= budget["transferred_bytes"]
    ):
        return dict(action="stop", reason="protocol_budget")
    if receipts and receipts[-1]["status"] != "completed":
        return dict(action="stop", reason="last_capture_partial_requires_review")
    due = instant(receipts[-1]["captured_at"]) + timedelta(hours=1) if receipts else now
    if now < due:
        return dict(
            action="wait",
            seconds=min(30.0, max(0.01, (due - now).total_seconds())),
            next_capture_at=due.isoformat(),
        )
    return dict(action="capture")


def run_watch(
    protocol_dir, dataset, study, output, *, clock=utc, sleep=time.sleep, transport=None
):
    protocol_dir = Path(protocol_dir)
    protocol, history = observation_history(protocol_dir)
    output = new_output(
        output,
        inputs=[
            protocol_dir,
            Path(dataset),
            Path(study),
            Path(protocol["capture_root"]),
        ],
    )
    lock = Path(protocol["capture_root"]).with_name(
        Path(protocol["capture_root"]).name + ".watch-lock"
    )
    with lock.open("x") as f:
        os.chmod(lock, 0o600)
        f.write(str(os.getpid()))
    inode = lock.stat().st_ino
    state = dict(
        schema="crypto.watch_state.v1",
        pid=os.getpid(),
        started_at=clock().isoformat(),
        protocol_sha256=digest(protocol_dir / "protocol.json"),
        mode="bounded_read_only_research",
        status="running",
        maximum_hours=48,
        root_source_sha256=digest(Path(__file__)),
    )
    write_json(output / "state.json", state)
    try:
        while True:
            protocol, history = observation_history(protocol_dir)
            action = next_action(protocol, [r for _, r in history], clock())
            state.update(
                last_checked_at=clock().isoformat(),
                captures=len(history),
                next_action=action,
            )
            write_json(output / "state.json", state)
            if action["action"] == "stop":
                state.update(status="stopped", reason=action["reason"])
                break
            if action["action"] == "wait":
                sleep(action["seconds"])
                continue
            result = capture_observation(
                protocol_dir, transport or RecentTransport(), clock=clock
            )
            with (output / "events.jsonl").open("a") as f:
                f.write(
                    json.dumps(
                        dict(
                            at=clock().isoformat(),
                            status=result["status"],
                            observed_bars=len(result["observed_bars"]),
                            committed_forecasts=len(result["committed_forecasts"]),
                            scored_forecasts=len(result["scored_forecasts"]),
                        )
                    )
                    + "\n"
                )
            write_json(
                output / "health.json",
                monitor(dataset, study, protocol_dir, as_of=clock()),
            )
    except (Exception, KeyboardInterrupt) as exc:
        state.update(status="stopped", reason=type(exc).__name__)
    finally:
        state["stopped_at"] = clock().isoformat()
        write_json(output / "state.json", state)
        seal(output)
        if lock.exists() and lock.stat().st_ino == inode:
            lock.unlink()
    return state


def main():
    def interrupt(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, interrupt)
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ["protocol", "dataset", "study", "output"]:
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_watch(args.protocol, args.dataset, args.study, args.output)))


if __name__ == "__main__":
    main()
