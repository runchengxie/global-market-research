"""Resolve permanent project data from machine-local workspace settings."""

import os
from pathlib import Path
import tomllib

from ._project_storage import project_root


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def _default_workspace_files() -> list[Path]:
    config_home = _config_home()
    paths = [
        config_home / "quant-competition" / "shared" / "workspace.toml",
        config_home / Path.home().name / "shared" / "workspace.toml",
    ]
    unique: list[Path] = []
    for path in paths:
        if path not in unique:
            unique.append(path)
    return unique


def _workspace_config_file() -> Path:
    explicit = os.environ.get("WORKSPACE_CONFIG")
    if explicit is not None:
        return Path(explicit).expanduser()
    if "CONFIG_ROOT" in os.environ:
        return Path(os.environ["CONFIG_ROOT"]).expanduser() / "shared" / "workspace.toml"
    for path in _default_workspace_files():
        if path.is_file():
            return path
    return _default_workspace_files()[0]


def _workspace_data_root(settings: dict) -> object:
    nested = settings.get("roots", {})
    if "roots" in settings and not isinstance(nested, dict):
        raise ValueError("Workspace roots must be a table")
    if not isinstance(nested, dict):
        nested = {}
    candidates = []
    if "data_root" in settings:
        candidates.append(settings["data_root"])
    if "DATA_ROOT" in nested:
        candidates.append(nested["DATA_ROOT"])
    if "DATA_ROOT" in settings:
        candidates.append(settings["DATA_ROOT"])
    if not candidates:
        return None
    if len(set(candidates)) > 1:
        raise ValueError("Conflicting data_root / DATA_ROOT values")
    return candidates[0]


def load_data_root() -> Path:
    """Return this project's raw data directory, independent of its checkout."""
    data_root = os.environ.get("DATA_ROOT")
    settings = {}
    if data_root is None:
        config_file = _workspace_config_file()
        try:
            with config_file.open("rb") as stream:
                settings = tomllib.load(stream)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"Invalid workspace TOML in {config_file}: {exc}") from exc
        except OSError as exc:
            raise ValueError(
                f"Cannot read workspace configuration {config_file}. "
                "Set WORKSPACE_CONFIG to a readable workspace.toml file "
                "or DATA_ROOT to an absolute data directory."
            ) from exc
        data_root = _workspace_data_root(settings)

    if not isinstance(data_root, str) or not data_root.strip():
        raise ValueError("data_root / DATA_ROOT must be a non-empty absolute path")
    root = Path(data_root).expanduser()
    if not root.is_absolute():
        raise ValueError("data_root / DATA_ROOT must be an absolute path")
    # The permanent owner is fixed; a task worktree name must never select data.
    return project_root(root, settings.get("project_data_root")) / "research" / "crypto-mm" / "raw_data"
