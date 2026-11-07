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
