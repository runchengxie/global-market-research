"""Explicit single-attempt Linux Paper launcher; checks never start Java or connect."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import shlex
import xml.etree.ElementTree as ET
import subprocess
import sys
import uuid

from competition_tools.gateway_launcher import LauncherError, _ini, _pairs


class LaunchError(ValueError):
    """Stable, non-secret diagnostic code."""


def fail(code):
    raise LaunchError(code)


def checked_path(value, *, private=False, directory=False):
    if not isinstance(value, str):
        fail("INVALID_PATH")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        fail("INVALID_PATH")
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            fail("SYMLINK_PATH")
        if ancestor != path:
            parent_info = ancestor.stat()
            trusted_sticky = (
                parent_info.st_uid == 0 and parent_info.st_mode & stat.S_ISVTX
            )
            if parent_info.st_uid not in {0, os.getuid()} or (
                parent_info.st_mode & 0o022 and not trusted_sticky
            ):
                fail("UNSAFE_ANCESTOR")
        if (ancestor / ".git").exists() or ancestor.name == ".git":
            fail("PATH_IN_SOURCE")
    info = path.stat()
    if info.st_uid != os.getuid():
        fail("WRONG_OWNER")
    if directory != stat.S_ISDIR(info.st_mode):
        fail("INVALID_PATH_TYPE")
    if not directory and not stat.S_ISREG(info.st_mode):
        fail("INVALID_PATH_TYPE")
    if info.st_mode & (0o077 if private else 0o022):
        fail("UNSAFE_PERMISSIONS")
    if private:
        # Protect the immediate private container against rename/replacement.
        parent = path.parent.stat()
        if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
            fail("UNSAFE_PARENT_PERMISSIONS")
    return path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)


def gateway_running():
    """Conservatively exclude all Java sessions without reading their arguments."""
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            name = (entry / "comm").read_text().strip().lower()
        except FileNotFoundError:
            continue
        except PermissionError:
            fail("PROCESS_PROBE_FAILED")
        if name in {"java", "javaw", "ibgateway", "ibgateway1", "tws", "tws1"}:
            return True
    return False


@dataclass(frozen=True)
class Spec:
    config_path: Path
    argv: tuple[str, ...]
    settings: Path
    logs: Path
    authorized: bool
    timeout: int


def build_spec(config_path, *, process_probe=None, own_lease=False):
    """Validate only; never create files, launch a child, or open sockets."""
    try:
        if sys.platform != "linux":
            fail("LINUX_REQUIRED")
        config_path = checked_path(str(config_path), private=True)
        cfg = read_json(config_path)
        keys = {
            "schema_version",
            "gateway_directory",
            "ibc_directory",
            "ini_path",
            "settings_directory",
            "log_directory",
            "manifest_path",
            "activation_authorized",
            "timeout_seconds",
        }
        if (
            not isinstance(cfg, dict)
            or set(cfg) != keys
            or cfg["schema_version"] != "competition.linux_gateway.v1"
        ):
            fail("INVALID_CONFIGURATION")
        if (
            type(cfg["activation_authorized"]) is not bool
            or type(cfg["timeout_seconds"]) is not int
            or not 30 <= cfg["timeout_seconds"] <= 300
        ):
            fail("INVALID_CONFIGURATION")
        gateway = checked_path(cfg["gateway_directory"], directory=True)
        ibc = checked_path(cfg["ibc_directory"], directory=True)
        ini = checked_path(cfg["ini_path"], private=True)
        settings = checked_path(cfg["settings_directory"], private=True, directory=True)
        logs = checked_path(cfg["log_directory"], private=True, directory=True)
        # Fresh, isolated settings only: never reuse restart/session material.
        if any(settings.iterdir()):
            fail("SETTINGS_NOT_EMPTY")
        if not _ini(ini, cfg["timeout_seconds"]):
            fail("READ_ONLY_REQUIRED")
        credentials = {}
        for line in ini.read_text(encoding="utf-8-sig").splitlines():
            if line.startswith(("IbLoginId=", "IbPassword=")):
                key, value = line.split("=", 1)
                credentials[key] = bool(value.strip()) and "REPLACE_" not in value
        if credentials != {"IbLoginId": True, "IbPassword": True}:
            fail("CREDENTIALS_NOT_CONFIGURED")
        manifest_path = checked_path(cfg["manifest_path"], private=True)
        manifest = read_json(manifest_path)
        if not isinstance(manifest, dict) or not manifest:
            fail("INVALID_MANIFEST")
        verified = set()
        for name, digest in manifest.items():
            path = checked_path(name)
            if not (path.is_relative_to(gateway) or path.is_relative_to(ibc)):
                fail("MANIFEST_OUTSIDE_TOOLS")
            if (
                not isinstance(digest, str)
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest
            ):
                fail("INTEGRITY_FAILED")
            verified.add(path)
        jars = sorted((gateway / "jars").glob("*.jar"))
        java = gateway / "jre/bin/java"
        runtime = gateway / ".install4j/i4jruntime.jar"
        ibc_jar = ibc / "IBC.jar"
        vm_file = gateway / "ibgateway.vmoptions"
        java_config = gateway / ".install4j/i4jparams.conf"
        if (
            not jars
            or not {java, runtime, ibc_jar, vm_file, java_config, *jars} <= verified
        ):
            fail("INCOMPLETE_MANIFEST")
        if not os.access(java, os.X_OK):
            fail("JAVA_NOT_EXECUTABLE")
        vm = [
            line.strip()
            for line in vm_file.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "-D"))
        ]
        variables = ET.fromstring(java_config.read_text()).iter("variable")
        extra = [
            item.attrib["value"]
            for item in variables
            if item.get("name") == "javaOptions"
        ]
        if len(extra) != 1:
            fail("INVALID_JAVA_OPTIONS")
        # Only options from the reviewed immutable Gateway files are used.
        options = [
            *shlex.split(extra[0]),
            *vm,
            "-Dtwslaunch.autoupdate.serviceImpl=com.ib.tws.twslaunch.install4j.Install4jAutoUpdateService",
            "-Dchannel=latest",
            "-Dexe4j.isInstall4j=true",
            "-Dinstall4jType=standalone",
            f"-DjtsConfigDir={settings}",
            f"-Dibcsessionid={uuid.uuid4().hex}",
        ]
        argv = (
            str(java),
            *options,
            "-cp",
            ":".join(map(str, [*jars, runtime, ibc_jar])),
            "ibcalpha.ibc.IbcGateway",
            str(ini),
            "paper",
        )
        if not own_lease and (logs / "launch.lease").exists():
            fail("EXISTING_LEASE")
        if (process_probe or gateway_running)():
            fail("EXISTING_GATEWAY_OR_JAVA")
        return Spec(
            config_path,
            tuple(argv),
            settings,
            logs,
            cfg["activation_authorized"],
            cfg["timeout_seconds"],
        )
    except (LaunchError,):
        raise
    except LauncherError as exc:
        fail(str(exc))
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError):
        fail("CONFIGURATION_CHECK_FAILED")


def start(spec):
    """Explicit activation only. Never kill, restart or automatically retry a child."""
    if not spec.authorized:
        fail("ACTIVATION_REQUIRED")
    if not os.environ.get("DISPLAY"):
        fail("DESKTOP_REQUIRED")
    lease = spec.logs / "launch.lease"
    try:
        fd = os.open(lease, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        fail("EXISTING_LEASE")
    except OSError:
        fail("LEASE_FAILED")
    launched = False
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(
                json.dumps(
                    {
                        "supervisor_pid": os.getpid(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )
        # Revalidate after acquiring the lease; do not trust stale in-memory specs.
        current = build_spec(spec.config_path, own_lease=True)
        if not current.authorized or current.logs != spec.logs:
            fail("CONFIGURATION_CHANGED")
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            in {
                "DISPLAY",
                "XAUTHORITY",
                "HOME",
                "USER",
                "LOGNAME",
                "LANG",
                "LC_ALL",
                "XDG_RUNTIME_DIR",
                "DBUS_SESSION_BUS_ADDRESS",
            }
        }
        env["PATH"] = "/usr/bin:/bin"
        log = current.logs / f"launch-{uuid.uuid4().hex}.log"
        logfd = os.open(
            log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
        with os.fdopen(logfd, "wb") as output:
            child = subprocess.Popen(
                current.argv,
                cwd=current.settings,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            launched = True
            try:
                code = child.wait(timeout=current.timeout)
            except subprocess.TimeoutExpired:
                return {"status": "observation_timeout", "lease_retained": True}
        lease.unlink()
        return {"status": "exited", "exit_code": code, "lease_retained": False}
    except LaunchError:
        if not launched:
            lease.unlink(missing_ok=True)
        raise
    except OSError:
        if not launched:
            lease.unlink(missing_ok=True)
        fail("LAUNCH_FAILED")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "dry-run", "start"])
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    try:
        spec = build_spec(args.config)
        result = (
            start(spec)
            if args.action == "start"
            else {
                "status": "preflight_passed",
                "authentication": "not_checked",
                "api": "not_checked",
                "historical_data": "not_checked",
                "activation_authorized": spec.authorized,
            }
        )
        print(json.dumps(result))
        return (
            3
            if result["status"] == "observation_timeout"
            else (0 if result.get("exit_code", 0) == 0 else 2)
        )
    except LaunchError as exc:
        print(json.dumps({"status": "blocked", "issue_codes": [str(exc)]}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
