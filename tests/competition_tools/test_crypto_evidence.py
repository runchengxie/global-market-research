import csv
import hashlib
import io
import zipfile
from datetime import datetime, timezone, timedelta

import pytest
from competition_tools.datasets.binance_intraday import (
    normalize_hourly,
    aggregate_four,
    archive_url,
    freeze_intraday_plan,
)
from competition_tools.crypto_evidence import seal, verify_seal, new_output


def archive(month="2025-01", hours=24, close_offset=0):
    start = datetime.fromisoformat(month + "-01T00:00:00+00:00")
    divisor = 1000000 if month >= "2025-01" else 1000
    text = io.StringIO()
    writer = csv.writer(text)
    for i in range(hours):
        t = int((start + timedelta(hours=i)).timestamp()) * divisor
        writer.writerow(
            [
                t,
                100,
                110,
                90,
                105,
                2,
                t + 3600 * divisor - 1 + close_offset,
                0,
                1,
                0,
                0,
                0,
            ]
        )
    name = f"BTCUSDT-1h-{month}"
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w") as z:
        z.writestr(name + ".csv", text.getvalue())
    data = body.getvalue()
    return data, hashlib.sha256(data).hexdigest() + "  " + name + ".zip"


@pytest.mark.parametrize("month", ["2024-12", "2025-01"])
def test_timestamp_unit_and_complete_month(month):
    import calendar

    count = calendar.monthrange(int(month[:4]), int(month[5:]))[1] * 24
    data, checksum = archive(month, count)
    rows = normalize_hourly(data, checksum, "BTCUSDT", month)
    assert len(rows) == count and rows[0]["time_open"] == month + "-01T00:00:00Z"
    assert len(aggregate_four(rows)) == count // 4
    assert aggregate_four(rows)[0]["volume"] == 8


@pytest.mark.parametrize("kind", ["checksum", "missing", "close"])
def test_bad_archive_rejected(kind):
    data, checksum = archive(hours=24, close_offset=1 if kind == "close" else 0)
    if kind == "checksum":
        checksum = "0" * 64 + checksum[64:]
    with pytest.raises(ValueError):
        normalize_hourly(data, checksum, "BTCUSDT", "2025-01")


def test_exact_url_and_frozen_budget(tmp_path):
    with pytest.raises(ValueError):
        archive_url("BTCUSDT/../", "2025-01")
    plan = freeze_intraday_plan(
        tmp_path / "plan", now=datetime(2026, 11, 7, tzinfo=timezone.utc)
    )
    assert len(plan["resources"]) == 96 and plan["budget"]["attempts"] == 112
    with pytest.raises(FileExistsError):
        freeze_intraday_plan(tmp_path / "plan", now=datetime.now(timezone.utc))


def test_seal_rejects_extra_mutated_and_symlink_files(tmp_path):
    root = tmp_path / "artifact"
    root.mkdir()
    (root / "facts.json").write_text("{}")
    seal(root)
    assert verify_seal(root)["files"]
    (root / "extra").write_text("private")
    with pytest.raises(ValueError):
        verify_seal(root)
    (root / "extra").unlink()
    (root / "facts.json").write_text("changed")
    with pytest.raises(ValueError):
        verify_seal(root)


def test_output_cannot_modify_parent_evidence(tmp_path):
    parent = tmp_path / "source"
    parent.mkdir()
    (parent / "facts").write_text("x")
    seal(parent)
    with pytest.raises(ValueError):
        new_output(parent / "child", inputs=[parent])
    assert not (parent / "child").exists()


def test_claim_preserves_unknown_spend_and_rejects_repeat(tmp_path):
    from competition_tools.datasets.binance_intraday import acquire_intraday

    class Lost:
        def fetch(self, *args, **kwargs):
            raise TimeoutError("lost response")

    freeze_intraday_plan(
        tmp_path / "plan", now=datetime(2026, 11, 7, tzinfo=timezone.utc)
    )
    result = acquire_intraday(tmp_path / "plan/plan.json", tmp_path / "run", Lost())
    assert result["status"] == "partial" and result["budget"]["attempts"] == 1
    assert result["budget"]["unknown_spend"] is True
    with pytest.raises(FileExistsError):
        acquire_intraday(tmp_path / "plan/plan.json", tmp_path / "another", Lost())
    assert not (tmp_path / "another").exists()


def test_nested_seal_file_cannot_bypass_integrity(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "facts").write_text("a")
    seal(root)
    (root / "nested").mkdir()
    (root / "nested/seal.json").write_text("private")
    with pytest.raises(ValueError):
        verify_seal(root)


@pytest.mark.parametrize("member", ["../BTCUSDT-1h-2025-01.csv", "extra.csv"])
def test_unexpected_zip_member_is_rejected(member):
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w") as z:
        z.writestr(member, "x")
    data = body.getvalue()
    checksum = hashlib.sha256(data).hexdigest() + " BTCUSDT-1h-2025-01.zip"
    with pytest.raises(ValueError):
        normalize_hourly(data, checksum, "BTCUSDT", "2025-01")


def test_forecast_commit_must_precede_entry_and_bind_features():
    from competition_tools.evaluation.crypto_observation import validate_forecasts

    now = datetime(2026, 11, 7, 12, 30, tzinfo=timezone.utc)
    row = dict(
        candidate="price_only-1h",
        asset="BTCUSDT",
        feature_cutoff="2026-11-07T12:00:00Z",
        generated_at=now.isoformat(),
        entry_at="2026-11-07T13:00:00Z",
        exit_at="2026-11-07T14:00:00Z",
        prediction=0.01,
        prior_prediction=0.001,
        feature_sha256="a" * 64,
        checkpoint_sha256="b" * 64,
    )
    protocol = dict(
        models={"price_only-1h": {"sha256": "b" * 64}}, frozen_at="2026-11-07T12:15:00Z"
    )
    assert validate_forecasts(protocol, [row], now) == [row]
    row["entry_at"] = "2026-11-07T12:00:00Z"
    with pytest.raises(ValueError):
        validate_forecasts(protocol, [row], now)


def test_monitor_preserves_unknown_inputs_without_promoting(tmp_path):
    from competition_tools.evaluation.crypto_monitor import monitor

    result = monitor(
        tmp_path / "missing-data",
        tmp_path / "missing-study",
        tmp_path / "missing-observation",
        as_of=datetime.now(timezone.utc),
    )
    assert result["status"] == "blocked" and len(result["blocking_reasons"]) == 3
    assert (
        result["accepted_research"] is False and result["execution_authorized"] is False
    )


def test_observation_receipt_ids_do_not_break_history_validation(tmp_path):
    from competition_tools.evaluation.crypto_observation import (
        observation_history,
        canonical_hash,
    )
    from competition_tools.crypto_evidence import digest
    import json

    protocol_dir = tmp_path / "protocol"
    protocol_dir.mkdir()
    captures = tmp_path / "protocol.captures"
    captures.mkdir()
    protocol = dict(
        models={"price_only-1h": {"sha256": "b" * 64}},
        frozen_at="2026-11-07T12:15:00Z",
        capture_root=str(captures),
    )
    (protocol_dir / "protocol.json").write_text(json.dumps(protocol))
    seal(protocol_dir)
    row = dict(
        candidate="price_only-1h",
        asset="BTCUSDT",
        feature_cutoff="2026-11-07T12:00:00Z",
        generated_at="2026-11-07T12:30:00Z",
        entry_at="2026-11-07T13:00:00Z",
        exit_at="2026-11-07T14:00:00Z",
        prediction=0.01,
        prior_prediction=0.001,
        feature_sha256="a" * 64,
        checkpoint_sha256="b" * 64,
    )
    row["id"] = canonical_hash(
        [
            digest(protocol_dir / "protocol.json"),
            row["candidate"],
            row["asset"],
            row["entry_at"],
        ]
    )
    out = captures / "000001"
    out.mkdir()
    (out / "receipt.json").write_text(
        json.dumps(
            dict(
                protocol_sha256=digest(protocol_dir / "protocol.json"),
                previous_seal_sha256=None,
                committed_forecasts=[row],
                captured_at="2026-11-07T12:30:01Z",
                http={"unknown_spend": False},
            )
        )
    )
    seal(out)
    assert len(observation_history(protocol_dir)[1]) == 1


@pytest.fixture
def observer(tmp_path, monkeypatch):
    import json
    import competition_tools.evaluation.crypto_observation as module
    from competition_tools.crypto_evidence import digest, read_json

    data = tmp_path / "data"
    data.mkdir()
    (data / "manifest.json").write_text(
        json.dumps({"end_exclusive": "2026-10-01T00:00:00Z"})
    )
    seal(data)
    study = tmp_path / "study"
    study.mkdir()
    (study / "models").mkdir()
    (study / "summary.json").write_text(
        json.dumps(dict(status="completed", fit_count=24, source_revision="a" * 40))
    )
    (study / "plan.json").write_text(
        json.dumps({"dataset_seal_sha256": digest(data / "seal.json")})
    )
    for step in [1, 4]:
        (study / "models" / f"{step}h-2-price_only.json").write_text(
            json.dumps(
                dict(
                    arm="price_only",
                    step_hours=step,
                    fit_last_exit="2026-07-31T00:00:00Z",
                )
            )
        )
    seal(study)
    clock = {"now": datetime(2026, 11, 7, 12, 30, tzinfo=timezone.utc)}

    def producer(python, args, **kwargs):
        if args == ["fingerprint"]:
            return {"files": {"source.py": "a" * 64}}
        opts = dict(zip(args[1::2], args[2::2]))
        protocol = read_json(opts["--protocol"])
        now = datetime.fromisoformat(opts["--generated-at"])
        result = []
        for candidate, binding in protocol["models"].items():
            step = int(candidate.split("-")[-1][0])
            cutoff = now.replace(
                hour=now.hour // step * step, minute=0, second=0, microsecond=0
            )
            for asset in ["BTCUSDT", "ETHUSDT"]:
                result.append(
                    dict(
                        candidate=candidate,
                        asset=asset,
                        feature_cutoff=cutoff.isoformat(),
                        generated_at=now.isoformat(),
                        entry_at=(cutoff + timedelta(hours=step)).isoformat(),
                        exit_at=(cutoff + timedelta(hours=2 * step)).isoformat(),
                        prediction=0.01,
                        prior_prediction=0.001,
                        feature_sha256="a" * 64,
                        checkpoint_sha256=binding["sha256"],
                    )
                )
        value = {"forecasts": result, "blocked": []}
        Path(opts["--output"]).write_text(json.dumps(value))
        return value

    from pathlib import Path

    monkeypatch.setattr(module, "_producer", producer)
    protocol = tmp_path / "protocol"
    module.freeze_observation(
        study,
        data,
        Path("/usr/bin/python3"),
        protocol,
        now=clock["now"] - timedelta(minutes=15),
    )

    class Transport:
        calls = 0

        def fetch(self, url, **kwargs):
            self.calls += 1
            now = clock["now"].replace(minute=0, second=0, microsecond=0)
            start = now - timedelta(hours=499)
            rows = []
            for i in range(500):
                t = int((start + timedelta(hours=i)).timestamp()) * 1000
                rows.append([t, 100, 110, 90, 101, 1, t + 3600000 - 1, 0, 1, 0, 0, 0])
            return 200, json.dumps(rows).encode()

    return module, protocol, clock, Transport()


def test_capture_commits_future_predictions_and_scores_only_matured(observer):
    module, protocol, clock, transport = observer
    first = module.capture_observation(protocol, transport, clock=lambda: clock["now"])
    assert first["status"] == "completed" and len(first["observed_bars"]) == 0
    assert len(first["committed_forecasts"]) == 4 and first["scored_forecasts"] == []
    clock["now"] += timedelta(hours=3)
    second = module.capture_observation(protocol, transport, clock=lambda: clock["now"])
    assert second["status"] == "completed" and len(second["observed_bars"]) == 2
    assert (
        len(second["committed_forecasts"]) == 2 and len(second["scored_forecasts"]) == 2
    )
    assert len(module.observation_history(protocol)[1]) == 2


def test_unknown_request_spend_stays_blocked_and_unknown_lock_is_preserved(observer):
    module, protocol, clock, transport = observer
    lock = protocol.with_name(protocol.name + ".captures.lock")
    lock.write_text("unknown")
    with pytest.raises(FileExistsError):
        module.capture_observation(protocol, transport, clock=lambda: clock["now"])
    assert transport.calls == 0 and lock.read_text() == "unknown"
    lock.unlink()

    class Lost:
        def fetch(self, *args, **kwargs):
            raise TimeoutError("unknown transfer")

    partial = module.capture_observation(protocol, Lost(), clock=lambda: clock["now"])
    assert partial["status"] == "partial" and partial["http"]["unknown_spend"]
    with pytest.raises(ValueError, match="UNKNOWN_OBSERVATION_SPEND"):
        module.capture_observation(protocol, transport, clock=lambda: clock["now"])
    assert transport.calls == 0


def test_output_rejects_any_sealed_ancestor_even_without_explicit_input(tmp_path):
    parent = tmp_path / "sealed"
    parent.mkdir()
    (parent / "facts").write_text("a")
    seal(parent)
    with pytest.raises(ValueError):
        new_output(parent / "report")
    assert not (parent / "report").exists()


def test_recent_capture_rejects_future_only_or_stale_history(observer):
    module, protocol, clock, transport = observer
    _, body = transport.fetch(module.recent_url("BTCUSDT"))
    assert len(module.normalize_recent(body, "BTCUSDT", clock["now"])) >= 170
    with pytest.raises(ValueError):
        module.normalize_recent(body, "BTCUSDT", clock["now"] - timedelta(days=100))
    with pytest.raises(ValueError):
        module.normalize_recent(body, "BTCUSDT", clock["now"] + timedelta(days=1))


def test_recent_worker_keeps_canonical_module_when_started_as_cli(monkeypatch):
    import competition_tools.evaluation.crypto_observation as module

    def run(command, **kwargs):
        assert command[2] == "competition_tools.evaluation.crypto_observation"
        return 200, b"[]"

    monkeypatch.setattr(module, "run_worker", run)
    monkeypatch.setattr(module, "__name__", "__main__")
    assert module.RecentTransport().fetch(
        module.recent_url("BTCUSDT"), max_bytes=1024, timeout=1
    ) == (200, b"[]")


def test_recovery_protocol_carries_reserved_unknown_spend(observer):
    module, protocol, clock, transport = observer

    class Lost:
        def fetch(self, *args, **kwargs):
            raise TimeoutError("unknown")

    module.capture_observation(protocol, Lost(), clock=lambda: clock["now"])
    recovered = module.freeze_observation(
        protocol.parent / "study",
        protocol.parent / "data",
        __import__("pathlib").Path("/usr/bin/python3"),
        protocol.parent / "recovered",
        now=clock["now"] + timedelta(minutes=1),
        previous_protocol=protocol,
    )
    assert recovered["budget"]["http_attempts"] == 95
    assert recovered["budget"]["captures"] == 47
    assert recovered["budget"]["transferred_bytes"] == 31 * 1024**2
    assert recovered["predecessor"]["reserved_unknown_bytes"] == 1024**2


def test_late_backfill_is_not_a_timely_prospective_observation(observer):
    module, protocol, clock, transport = observer
    module.capture_observation(protocol, transport, clock=lambda: clock["now"])
    clock["now"] += timedelta(hours=3)
    result = module.capture_observation(protocol, transport, clock=lambda: clock["now"])
    assert len(result["observed_bars"]) == 2
    assert len(result["late_received_bars"]) == 4


def test_bounded_watch_waits_then_stops_for_partial_or_budget():
    from competition_tools.evaluation.crypto_watch import next_action

    frozen = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    protocol = dict(
        frozen_at=frozen.isoformat(),
        budget=dict(captures=2, http_attempts=4, transferred_bytes=10000),
    )
    receipt = dict(
        captured_at=frozen.isoformat(),
        status="completed",
        http=dict(attempts=2, bytes=100),
    )
    assert (
        next_action(protocol, [receipt], frozen + timedelta(minutes=10))["action"]
        == "wait"
    )
    assert (
        next_action(protocol, [receipt], frozen + timedelta(hours=1))["action"]
        == "capture"
    )
    assert (
        next_action(protocol, [receipt, receipt], frozen + timedelta(hours=2))["action"]
        == "stop"
    )
    receipt["status"] = "partial"
    assert (
        next_action(protocol, [receipt], frozen + timedelta(hours=1))["action"]
        == "stop"
    )


def test_worker_terminates_child_on_interrupt(monkeypatch):
    import competition_tools.crypto_evidence as evidence

    class Process:
        calls = 0
        killed = False
        returncode = 0

        def communicate(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise KeyboardInterrupt()
            return b"", b""

        def kill(self):
            self.killed = True

    process = Process()
    monkeypatch.setattr(evidence.subprocess, "Popen", lambda *a, **k: process)
    with pytest.raises(KeyboardInterrupt):
        evidence.bounded_worker(["unused"], timeout=1, max_bytes=100)
    assert process.killed and process.calls == 2


def test_capture_cli_returns_nonzero_for_partial(monkeypatch, tmp_path):
    import sys
    import competition_tools.evaluation.crypto_observation as module

    monkeypatch.setattr(
        module,
        "capture_observation",
        lambda *a, **k: dict(
            status="partial",
            observed_bars=[],
            committed_forecasts=[],
            scored_forecasts=[],
            reason="failed",
        ),
    )
    monkeypatch.setattr(
        sys, "argv", ["observe", "capture", "--protocol", str(tmp_path / "protocol")]
    )
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2


def test_freeze_cli_forwards_predecessor_parameter(monkeypatch, tmp_path):
    import sys
    import competition_tools.evaluation.crypto_observation as module

    received = {}

    def freeze(*args, **kwargs):
        received.update(kwargs)
        return {"schema": "test", "frozen_at": "2026-11-07T12:00:00Z"}

    monkeypatch.setattr(module, "freeze_observation", freeze)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "observe",
            "freeze",
            "--study",
            str(tmp_path / "study"),
            "--dataset",
            str(tmp_path / "data"),
            "--producer-python",
            "/usr/bin/python3",
            "--output",
            str(tmp_path / "new"),
            "--previous-protocol",
            str(tmp_path / "previous"),
        ],
    )
    module.main()
    assert received["previous_protocol"] == tmp_path / "previous"


def test_failed_start_budget_debit_preserves_existing_forecasts(observer):
    module, old, clock, transport = observer
    from competition_tools.crypto_evidence import digest

    class Lost:
        def fetch(self, *a, **k):
            raise TimeoutError("unknown")

    module.capture_observation(old, Lost(), clock=lambda: clock["now"])
    clock["now"] += timedelta(minutes=2)
    fresh = old.parent / "fresh"
    module.freeze_observation(
        old.parent / "study",
        old.parent / "data",
        __import__("pathlib").Path("/usr/bin/python3"),
        fresh,
        now=clock["now"],
    )
    module.capture_observation(fresh, transport, clock=lambda: clock["now"])
    before = digest(fresh / "protocol.json")
    receipt = fresh.with_name("fresh.captures") / "000001/seal.json"
    receipt_hash = digest(receipt)
    module.reconcile_failed_start(fresh, old, now=clock["now"])
    effective, history = module.observation_history(fresh)
    assert (
        effective["budget"]["http_attempts"] == 95
        and len(history[0][1]["committed_forecasts"]) == 4
    )
    assert digest(fresh / "protocol.json") == before and digest(receipt) == receipt_hash


def test_bounded_watch_process_completes_with_no_system_scheduler(observer, tmp_path):
    import json
    from competition_tools.evaluation.crypto_watch import run_watch
    from competition_tools.crypto_evidence import read_json, verify_seal

    module, protocol, clock, transport = observer
    config = read_json(protocol / "protocol.json")
    config["budget"].update(captures=2, http_attempts=4)
    (protocol / "seal.json").unlink()
    (protocol / "protocol.json").write_text(json.dumps(config))
    seal(protocol)

    def sleep(seconds):
        clock["now"] += timedelta(seconds=seconds)

    result = run_watch(
        protocol,
        protocol.parent / "data",
        protocol.parent / "study",
        tmp_path / "watch",
        clock=lambda: clock["now"],
        sleep=sleep,
        transport=transport,
    )
    assert result["status"] == "stopped" and result["reason"] == "protocol_budget"
    assert transport.calls == 4
    assert not protocol.with_name(protocol.name + ".captures.watch-lock").exists()
    verify_seal(tmp_path / "watch")


def test_acquisition_deadline_covers_final_aggregation_and_writes(
    tmp_path, monkeypatch
):
    import types
    import competition_tools.datasets.binance_intraday as module

    clock = {"elapsed": 0.0}
    monkeypatch.setattr(
        module,
        "time",
        types.SimpleNamespace(monotonic=lambda: clock["elapsed"], sleep=lambda _: None),
    )

    def normalize(body, checksum, product, month):
        return [
            dict(
                asset=product,
                time_open=month + "-01T00:00:00Z",
                interval_end=month + "-01T01:00:00Z",
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1.0,
            )
        ]

    monkeypatch.setattr(module, "normalize_hourly", normalize)

    def final(rows):
        clock["elapsed"] = 601.0
        return rows

    monkeypatch.setattr(module, "aggregate_four", final)

    class Transport:
        def fetch(self, url, **kwargs):
            clock["elapsed"] = 590.0
            if url.endswith(".CHECKSUM"):
                return 200, b"checksum"
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w") as z:
                z.writestr("synthetic.csv", "x")
            return 200, data.getvalue()

    module.freeze_intraday_plan(
        tmp_path / "plan", now=datetime(2026, 11, 7, tzinfo=timezone.utc)
    )
    result = module.acquire_intraday(
        tmp_path / "plan/plan.json", tmp_path / "run", Transport()
    )
    assert result["status"] == "partial" and "DEADLINE" in result["budget"]["reason"]
    assert result["budget"]["completed_resources"] == 96


def test_completed_seal_cannot_override_acquisition_budget(tmp_path):
    import json
    from competition_tools.datasets.binance_intraday import verify_intraday, PRODUCTS

    folder = tmp_path / "artifact"
    folder.mkdir()
    manifest = dict(
        schema="crypto.hourly_manifest.v1",
        status="completed",
        accepted_research=False,
        products=PRODUCTS,
        budget=dict(
            status="completed",
            attempts=96,
            transferred_bytes=1000,
            expanded_bytes=1000,
            unknown_spend=False,
            completed_resources=96,
            elapsed_seconds=601.0,
        ),
    )
    (folder / "manifest.json").write_text(json.dumps(manifest))
    seal(folder)
    with pytest.raises(ValueError):
        verify_intraday(folder)
