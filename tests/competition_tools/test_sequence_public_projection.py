import hashlib
import json
from pathlib import Path
import runpy
import pytest

module = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "scripts/sequence_public_projection.py")
)


def bundle(path, name, value):
    path.mkdir()
    raw = json.dumps(value).encode()
    (path / name).write_bytes(raw)
    (path / "checksums.json").write_text(
        json.dumps({name: hashlib.sha256(raw).hexdigest()})
    )


def test_publication_source_rejects_unsealed_extra_files(tmp_path):
    bundle(tmp_path / "bundle", "summary.json", {"status": "completed"})
    assert (
        module["verified"](tmp_path / "bundle", "summary.json")["status"] == "completed"
    )
    (tmp_path / "bundle" / "unsealed.json").write_text("{}")
    with pytest.raises(ValueError, match="SOURCE"):
        module["verified"](tmp_path / "bundle", "summary.json")


def test_hardcoded_sample_cannot_publish_another_snapshot(tmp_path):
    bundle(
        tmp_path / "primary",
        "config.json",
        {"inputs": {"manifest.json": {"sha256": "a" * 64}}},
    )
    bundle(
        tmp_path / "diagnostic",
        "summary.json",
        {
            "status": "completed",
            "records": 350,
            "source": {"data_manifest_sha256": "a" * 64},
        },
    )
    with pytest.raises(ValueError, match="SCOPE"):
        module["project"](tmp_path / "primary", tmp_path / "diagnostic")


def test_export_output_cannot_mutate_a_source_bundle(tmp_path, monkeypatch):
    import sys

    bundle(tmp_path / "source", "summary.json", {"ready": True})
    parent = tmp_path / "source"
    before = (parent / "checksums.json").read_bytes()
    monkeypatch.setitem(
        module["main"].__globals__, "project", lambda *args: {"schema": "test"}
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "projection",
            "--primary",
            str(parent),
            "--diagnostics",
            str(parent),
            "--output",
            str(parent / "public.json"),
        ],
    )
    with pytest.raises(ValueError, match="SEPARATE"):
        module["main"]()
    assert not (parent / "public.json").exists()
    assert (parent / "checksums.json").read_bytes() == before
