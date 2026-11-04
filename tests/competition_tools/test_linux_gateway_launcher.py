"""Synthetic launch contracts: no broker credentials or real Java execution."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from competition_tools import linux_gateway_launcher as lg

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux-only launcher")


@pytest.fixture
def config(tmp_path):
    root = tmp_path / "deployment"
    root.mkdir(mode=0o700)
    for n in ("settings", "logs", "gateway", "ibc"):
        (root / n).mkdir(mode=0o700)
    gateway = root / "gateway"
    (gateway / "jars").mkdir()
    (gateway / ".install4j").mkdir()
    (gateway / "jre/bin").mkdir(parents=True)
    files = [
        "jars/api.jar",
        ".install4j/i4jruntime.jar",
        "jre/bin/java",
        "ibgateway.vmoptions",
        ".install4j/i4jparams.conf",
    ]
    for n in files:
        (gateway / n).write_text("-Xmx512m\n" if n.endswith("vmoptions") else "fake")
    (gateway / ".install4j/i4jparams.conf").write_text(
        '<config><variable name="javaOptions" value="--add-opens=java.base/java.util=ALL-UNNAMED" /></config>'
    )
    (gateway / "jre/bin/java").chmod(0o700)
    (root / "ibc/IBC.jar").write_text("fake ibc")
    for item in root.rglob("*"):
        if item.is_dir():
            item.chmod(0o700)
        if item.is_file():
            item.chmod(0o700 if item.name == "java" else 0o600)
    ini = root / "ibc.ini"
    ini.write_text(
        "TradingMode=paper\nReadOnlyApi=yes\nReadOnlyLogin=no\nExistingSessionDetectedAction=manual\nReloginAfterSecondFactorAuthenticationTimeout=no\nSecondFactorAuthenticationExitInterval=120\nFIX=no\nCommandServerPort=0\nIbLoginId=SYNTHETIC_USER\nIbPassword=SYNTHETIC_SECRET\n"
    )
    ini.chmod(0o600)
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in [*(gateway / n for n in files), root / "ibc/IBC.jar"]
            }
        )
    )
    manifest.chmod(0o600)
    cfg = dict(
        schema_version="competition.linux_gateway.v1",
        gateway_directory=str(gateway),
        ibc_directory=str(root / "ibc"),
        ini_path=str(ini),
        settings_directory=str(root / "settings"),
        log_directory=str(root / "logs"),
        manifest_path=str(manifest),
        activation_authorized=False,
        timeout_seconds=120,
    )
    path = root / "launcher.json"
    path.write_text(json.dumps(cfg))
    path.chmod(0o600)
    return path, cfg


def check(config, **kwargs):
    return lg.build_spec(config[0], process_probe=lambda: False, **kwargs)


def test_check_is_read_only_and_redacted(config):
    before = sorted(str(p) for p in config[0].parent.rglob("*"))
    spec = check(config)
    assert "ibcalpha.ibc.IbcGateway" in spec.argv
    assert spec.argv[-1] == "paper"
    assert "--add-opens=java.base/java.util=ALL-UNNAMED" in spec.argv
    assert "SYNTHETIC_" not in repr(spec)
    assert sorted(str(p) for p in config[0].parent.rglob("*")) == before


@pytest.mark.parametrize(
    "change",
    [
        "permissions",
        "symlink",
        "duplicate",
        "unknown",
        "live",
        "writable",
        "placeholder",
        "continuation",
        "tamper",
        "process",
        "lease",
    ],
)
def test_unsafe_inputs_fail_closed(config, change):
    path, cfg = config
    ini = Path(cfg["ini_path"])
    if change == "permissions":
        ini.chmod(0o644)
    elif change == "symlink":
        other = ini.with_suffix(".real")
        ini.rename(other)
        ini.symlink_to(other)
    elif change == "duplicate":
        ini.write_text(ini.read_text() + "ReadOnlyApi=yes\n")
    elif change == "unknown":
        ini.write_text(ini.read_text() + "AccessToken=SYNTHETIC_SECRET\n")
    elif change == "live":
        ini.write_text(ini.read_text().replace("TradingMode=paper", "TradingMode=live"))
    elif change == "writable":
        ini.write_text(ini.read_text().replace("ReadOnlyApi=yes", "ReadOnlyApi=no"))
    elif change == "placeholder":
        ini.write_text(ini.read_text().replace("SYNTHETIC_USER", "REPLACE_WITH_ID"))
    elif change == "continuation":
        ini.write_text(ini.read_text() + "IbPassword=secret\\\n")
    elif change == "tamper":
        (Path(cfg["ibc_directory"]) / "IBC.jar").write_text("tampered")
    elif change == "lease":
        (Path(cfg["log_directory"]) / "launch.lease").touch()

    def probe():
        return change == "process"

    with pytest.raises(lg.LaunchError) as exc:
        lg.build_spec(path, process_probe=probe)
    assert "SYNTHETIC" not in str(exc.value)


def test_start_requires_activation_and_desktop(config, monkeypatch):
    spec = check(config)
    with pytest.raises(lg.LaunchError, match="ACTIVATION_REQUIRED"):
        lg.start(spec)
    config[1]["activation_authorized"] = True
    config[0].write_text(json.dumps(config[1]))
    spec = check(config)
    monkeypatch.delenv("DISPLAY", raising=False)
    with pytest.raises(lg.LaunchError, match="DESKTOP_REQUIRED"):
        lg.start(spec)


@pytest.mark.parametrize("timeout", [False, True])
def test_single_child_and_lease_lifecycle(config, monkeypatch, timeout):
    config[1]["activation_authorized"] = True
    config[0].write_text(json.dumps(config[1]))
    spec = check(config)
    monkeypatch.setenv("DISPLAY", ":synthetic")
    monkeypatch.setattr(lg, "gateway_running", lambda: False)
    calls = []

    class Child:
        pid = 99999

        def wait(self, timeout):
            if timeout and test_timeout:
                raise subprocess.TimeoutExpired("synthetic", timeout)
            return 0

    test_timeout = timeout

    def spawn(argv, **kwargs):
        calls.append((argv, kwargs))
        return Child()

    monkeypatch.setattr(lg.subprocess, "Popen", spawn)
    result = lg.start(spec)
    assert len(calls) == 1
    assert "SYNTHETIC_SECRET" not in repr(calls)
    assert result["status"] == ("observation_timeout" if timeout else "exited")
    assert (Path(config[1]["log_directory"]) / "launch.lease").exists() == timeout


@pytest.mark.parametrize("kind", ["private", "tools"])
def test_writable_ancestor_rejected(config, kind):
    root = config[0].parent
    if kind == "private":
        root.chmod(0o777)
    else:
        (Path(config[1]["gateway_directory"]) / "jars").chmod(0o777)
    with pytest.raises(lg.LaunchError, match="UNSAFE_ANCESTOR"):
        check(config)
