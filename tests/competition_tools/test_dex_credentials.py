import json
import os
import subprocess

import pytest

from competition_tools.datasets import dex_credentials as credentials


def setup(tmp_path):
    code, config = tmp_path / "code", tmp_path / "private"
    source = code / "global-market-research/.env"
    source.parent.mkdir(parents=True)
    (source.parent / ".git").mkdir()
    source.write_bytes(
        b"OTHER=value\r\nDEXPAPRIKA_API_KEY='fixture-only'\r\n# retain\n"
    )
    workspace = tmp_path / "workspace.toml"
    workspace.write_text(
        f'code_root = "{code.as_posix()}"\nconfig_root = "{config.as_posix()}"\ndata_root = "{(tmp_path / "data").as_posix()}"\n'
    )
    return (
        source,
        config / "projects/2026-quant-competition/providers/dexpaprika.env",
        workspace,
    )


def test_migration_preserves_unrelated_bytes_and_recovers(tmp_path, capsys):
    source, destination, workspace = setup(tmp_path)
    result = credentials.migrate_key(source, destination, workspace)
    assert result == {"status": "migrated"}
    assert source.read_bytes() == b"OTHER=value\r\n# retain\n"
    assert credentials.load_key(destination) == "fixture-only"
    assert "fixture-only" not in json.dumps(result) + str(capsys.readouterr())
    assert credentials.migrate_key(source, destination, workspace) == {
        "status": "already_migrated"
    }
    assert list(destination.parent.glob(".dexpaprika-recovery-*"))


def test_windows_migration_removes_explicit_foreign_grants(tmp_path):
    source, destination, workspace = setup(tmp_path)
    credentials.migrate_key(source, destination, workspace)
    if os.name != "nt":
        assert destination.stat().st_mode & 0o777 == 0o600
        return
    path = str(destination).replace("'", "''")
    script = (
        "$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value; $acl=Get-Acl -LiteralPath '"
        + path
        + "'; $foreign=@($acl.Access | Where-Object {$_.AccessControlType -eq 'Allow' -and $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -ne $sid}); if (-not $acl.AreAccessRulesProtected -or $foreign.Count -ne 0) {exit 2}"
    )
    environment = {k: v for k, v in os.environ.items() if k.upper() != "PSMODULEPATH"}
    checked = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        capture_output=True,
        timeout=30,
        env=environment,
    )
    assert checked.returncode == 0


def test_duplicate_key_is_not_silently_selected(tmp_path):
    path = tmp_path / "provider.env"
    path.write_text("DEXPAPRIKA_API_KEY=first\nDEXPAPRIKA_API_KEY=second\n")
    with pytest.raises(ValueError, match="DUPLICATE_CREDENTIAL"):
        credentials.load_key(path)


@pytest.mark.parametrize(
    "value", ["", "${OTHER}", '"line\\nvalue"', "abc # comment", "'unfinished"]
)
def test_unsupported_values_are_rejected_without_echo(tmp_path, value):
    path = tmp_path / "provider.env"
    path.write_text("DEXPAPRIKA_API_KEY=" + value)
    with pytest.raises(ValueError, match="INVALID_CREDENTIAL"):
        credentials.load_key(path)


def test_conflict_keeps_source_and_destination(tmp_path):
    source, destination, workspace = setup(tmp_path)
    destination.parent.mkdir(parents=True)
    destination.write_text("DEXPAPRIKA_API_KEY=different\n")
    before = source.read_bytes()
    with pytest.raises(ValueError, match="CREDENTIAL_CONFLICT"):
        credentials.migrate_key(source, destination, workspace)
    assert source.read_bytes() == before
    assert "different" in destination.read_text()


def test_failure_before_source_replacement_keeps_recovery(tmp_path, monkeypatch):
    source, destination, workspace = setup(tmp_path)
    before = source.read_bytes()

    def fail(*args):
        raise OSError("synthetic interruption")

    monkeypatch.setattr(credentials, "_replace_source", fail)
    with pytest.raises(ValueError, match="MIGRATION_INTERRUPTED"):
        credentials.migrate_key(source, destination, workspace)
    assert source.read_bytes() == before
    assert credentials.load_key(destination) == "fixture-only"
    assert list(destination.parent.glob(".dexpaprika-recovery-*"))


def test_wrong_source_and_repository_destination_are_rejected(tmp_path):
    source, destination, workspace = setup(tmp_path)
    with pytest.raises(ValueError):
        credentials.migrate_key(source, source.parent / "provider.env", workspace)
    with pytest.raises(ValueError):
        credentials.migrate_key(source.parent / "other.env", destination, workspace)


def test_shared_config_root_cannot_be_used_as_provider_destination(tmp_path):
    source, destination, workspace = setup(tmp_path)
    shared = destination.parents[3] / "shared.env"
    before = source.read_bytes()
    with pytest.raises(ValueError, match="INVALID_MIGRATION_PATH"):
        credentials.migrate_key(source, shared, workspace)
    assert source.read_bytes() == before


def test_utf8_bom_assignment_preserves_other_content(tmp_path):
    source, destination, workspace = setup(tmp_path)
    source.write_bytes(
        b"\xef\xbb\xbfDEXPAPRIKA_API_KEY=fixture-only\r\nOTHER=value\r\n"
    )
    assert (
        credentials.migrate_key(source, destination, workspace)["status"] == "migrated"
    )
    assert source.read_bytes() == b"\xef\xbb\xbfOTHER=value\r\n"


def test_reparse_credential_paths_are_rejected(tmp_path):
    target = tmp_path / "real.env"
    target.write_text("DEXPAPRIKA_API_KEY=fixture-only")
    link = tmp_path / "link.env"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation privilege unavailable")
    with pytest.raises(ValueError):
        credentials.load_key(link)


def test_canonical_credential_destination_is_supported_without_exposure(
    tmp_path, capsys
):
    source, old, workspace = setup(tmp_path)
    canonical = old.parents[2] / "global-market-research/providers/dexpaprika.env"
    assert credentials.migrate_key(source, canonical, workspace) == {
        "status": "migrated"
    }
    assert credentials.load_key(canonical) == "fixture-only"
    assert source.read_bytes() == b"OTHER=value\r\n# retain\n"
    assert not old.exists()
    assert credentials.migrate_key(source, canonical, workspace) == {
        "status": "already_migrated"
    }
    assert "fixture-only" not in str(capsys.readouterr())


@pytest.mark.parametrize(
    "target_name", ["global-market-research", "2026-quant-competition"]
)
def test_two_credential_namespaces_require_explicit_reconciliation(
    tmp_path, target_name
):
    source, old, workspace = setup(tmp_path)
    canonical = old.parents[2] / "global-market-research/providers/dexpaprika.env"
    target = canonical if target_name == "global-market-research" else old
    other = old if target == canonical else canonical
    other.parent.mkdir(parents=True)
    other.write_bytes(b"DEXPAPRIKA_API_KEY=fixture-only\n")
    before = source.read_bytes()
    kept = other.read_bytes()
    with pytest.raises(ValueError, match="CREDENTIAL_NAMESPACE_CONFLICT"):
        credentials.migrate_key(source, target, workspace)
    assert (
        not target.exists()
        and source.read_bytes() == before
        and other.read_bytes() == kept
    )


def test_concurrent_namespace_migrations_cannot_create_two_authorities(
    tmp_path, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    source, legacy, workspace = setup(tmp_path)
    canonical = legacy.parents[2] / "global-market-research/providers/dexpaprika.env"
    entered, release = Event(), Event()
    original = credentials._secure_write

    def pause_recovery(path, body):
        if path.name.startswith(".dexpaprika-recovery-"):
            entered.set()
            release.wait(20)
        return original(path, body)

    monkeypatch.setattr(credentials, "_secure_write", pause_recovery)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(credentials.migrate_key, source, canonical, workspace)
        assert entered.wait(5)
        second = pool.submit(credentials.migrate_key, source, legacy, workspace)
        try:
            with pytest.raises(ValueError, match="CREDENTIAL_MIGRATION_LOCKED"):
                second.result(timeout=5)
        finally:
            release.set()
        assert first.result(timeout=5) == {"status": "migrated"}
    assert canonical.exists() and not legacy.exists()


def test_unknown_migration_lock_is_not_removed_or_retried(tmp_path):
    source, destination, workspace = setup(tmp_path)
    lock = (
        destination.parents[3]
        / ".global-market-research-guards/dexpaprika-migration.lock"
    )
    lock.parent.mkdir(parents=True)
    lock.write_bytes(b"unknown previous attempt")
    before = source.read_bytes()
    with pytest.raises(ValueError, match="CREDENTIAL_MIGRATION_LOCKED"):
        credentials.migrate_key(source, destination, workspace)
    assert lock.read_bytes() == b"unknown previous attempt"
    assert source.read_bytes() == before and not destination.exists()
