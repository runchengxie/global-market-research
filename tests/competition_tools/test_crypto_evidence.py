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
    assert second["status"] == "completed" and len(second["observed_bars"]) == 6
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
