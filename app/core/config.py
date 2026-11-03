"""
Application configuration loaded from a JSON settings file.

The config file path defaults to ``PROJECT_ROOT/config/settings.json`` and can
be overridden by setting the ``CONFIG_PATH`` environment variable (useful for
tests or per-environment overrides).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path Constants
# ---------------------------------------------------------------------------
APP_DIR: Path = Path(__file__).resolve().parent.parent
PROJECT_ROOT: Path = APP_DIR.parent
STATIC_DIR: Path = APP_DIR / "static"
TEMPLATES_DIR: Path = APP_DIR / "templates"
DATA_DIR: Path = PROJECT_ROOT / "data"
CONFIG_DIR: Path = PROJECT_ROOT / "config"
DEFAULT_UPDATES_DIR: Path = PROJECT_ROOT / "updates"

_DEFAULT_CONFIG_PATH: Path = CONFIG_DIR / "settings.json"


# ---------------------------------------------------------------------------
# Configuration Dataclass
# ---------------------------------------------------------------------------
@dataclass
class AppConfig:
    """Typed representation of the application configuration."""

    app_name: str = "Update Manager"
    version: str = "1.0.0"
    debug: bool = False
    base_url: str = "https://sasthashub.duckdns.org"
    updates_dir: str = "updates"
    version_sort_strategy: str = "upload_time"  # "upload_time" or "semver"
    features: dict[str, Any] = field(default_factory=dict)


def get_updates_dir() -> Path:
    """Resolve and return the updates directory path."""
    env_dir = os.getenv("UPDATES_DIR")
    if env_dir:
        return Path(env_dir)
    config = get_config()
    cfg_dir = config.updates_dir
    p = Path(cfg_dir)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


# ---------------------------------------------------------------------------
# Singleton Config Loader
# ---------------------------------------------------------------------------
_config: AppConfig | None = None


def _resolve_config_path() -> Path:
    """Return the config file path, honouring the ``CONFIG_PATH`` env var."""
    env_path = os.getenv("CONFIG_PATH")
    if env_path:
        return Path(env_path)
    return _DEFAULT_CONFIG_PATH


def _load_from_file(path: Path) -> AppConfig:
    """Read a JSON file and return a populated :class:`AppConfig`."""
    data: dict[str, Any] = {}
    if path.exists():
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            data = {}

    return AppConfig(
        app_name=data.get("app_name", AppConfig.app_name),
        version=data.get("version", AppConfig.version),
        debug=data.get("debug", AppConfig.debug),
        base_url=data.get("base_url", AppConfig.base_url),
        updates_dir=data.get("updates_dir", AppConfig.updates_dir),
        version_sort_strategy=data.get("version_sort_strategy", AppConfig.version_sort_strategy),
        features=data.get("features", {}),
    )


def get_config() -> AppConfig:
    """Return the cached :class:`AppConfig`, loading it on first call."""
    global _config
    if _config is None:
        _config = _load_from_file(_resolve_config_path())
    return _config


def reload_config() -> AppConfig:
    """Force-reload the configuration from disk and return the new config."""
    global _config
    _config = _load_from_file(_resolve_config_path())
    return _config


# ---------------------------------------------------------------------------
# ROUTE_PATH Helper
# ---------------------------------------------------------------------------
def get_route_path() -> str:
    """Resolve and return the ``ROUTE_PATH`` value from the environment.

    The ``ROUTE_PATH`` env var is stripped of leading/trailing slashes and
    prefixed with ``/`` when non-empty.  An empty or unset value yields ``""``.
    """
    raw = os.getenv("ROUTE_PATH", "").strip("/")
    return f"/{raw}" if raw else ""
