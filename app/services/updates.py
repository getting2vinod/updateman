"""
Update management business logic: filesystem scanning, builds storage,
version discovery, rollback, and checksum verification.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packaging import version as pkg_version

from app import database
from app.core.config import get_config, get_updates_dir


def sanitize_path_segment(name: str) -> str:
    """Sanitize directory or filename components to prevent path traversal."""
    cleaned = re.sub(r"[^\w\.\-\+]", "_", name.strip())
    # Prevent directory traversal attacks
    if not cleaned or cleaned in (".", "..") or cleaned.startswith("."):
        raise ValueError(f"Invalid path segment: '{name}'")
    return cleaned


def normalize_target_devices(devices_input: str | None) -> str:
    """Normalizes device input string into comma-separated list or '*'."""
    if not devices_input or not devices_input.strip():
        return "*"
    tokens = [t.strip() for t in devices_input.split(",") if t.strip()]
    if "*" in tokens or not tokens:
        return "*"
    return ", ".join(tokens)


def is_device_allowed(target_devices: str | list[str] | None, device_id: str) -> bool:
    """
    Checks if a device ID is allowed by target_devices.
    If target_devices contains '*', any device is allowed.
    Otherwise, device_id must be in the list of target devices (case-insensitive).
    """
    if not target_devices:
        return True

    if isinstance(target_devices, str):
        devices = [d.strip().lower() for d in target_devices.split(",") if d.strip()]
    else:
        devices = [str(d).strip().lower() for d in target_devices if str(d).strip()]

    if "*" in devices or not devices:
        return True

    clean_device = device_id.strip().lower()
    return clean_device in devices


def compute_sha256(data: bytes) -> str:
    """Compute sha256 hex digest for binary content."""
    hasher = hashlib.sha256()
    hasher.update(data)
    return hasher.hexdigest()


def compute_file_sha256(filepath: Path) -> str:
    """Compute sha256 hex digest for a file on disk."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as fh:
        while chunk := fh.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _parse_semver_safe(v_str: str) -> tuple[int, Any]:
    """Attempts to parse a version string for semver comparison."""
    clean_v = v_str.lstrip("vV")
    try:
        return (1, pkg_version.parse(clean_v))
    except Exception:
        return (0, v_str)


def get_version_info(app_name: str, version_folder: str) -> dict[str, Any]:
    """Inspects a version directory on disk and returns its metadata."""
    base_dir = get_updates_dir() / app_name / version_folder
    if not base_dir.is_dir():
        raise FileNotFoundError(f"Version directory not found: {base_dir}")

    meta_file = base_dir / "metadata.json"
    version_file = base_dir / "version.txt"

    metadata: dict[str, Any] = {}
    if meta_file.exists():
        try:
            with open(meta_file, encoding="utf-8") as fh:
                metadata = json.load(fh)
        except Exception:
            metadata = {}

    # Version string
    version_str = version_folder
    if version_file.exists():
        try:
            with open(version_file, encoding="utf-8") as fh:
                content = fh.read().strip()
                if content:
                    version_str = content
        except Exception:
            pass

    # Find the binary file (exclude version.txt and metadata.json)
    binary_name = metadata.get("filename")
    binary_size = metadata.get("file_size")
    sha256_hash = metadata.get("sha256")

    files_in_dir = [
        f
        for f in base_dir.iterdir()
        if f.is_file() and f.name not in ("version.txt", "metadata.json")
    ]

    target_file: Path | None = None
    if binary_name and (base_dir / binary_name).is_file():
        target_file = base_dir / binary_name
    elif files_in_dir:
        # Choose the first binary file found
        target_file = sorted(files_in_dir, key=lambda f: f.stat().st_size, reverse=True)[0]
        binary_name = target_file.name

    if target_file and target_file.is_file():
        stat = target_file.stat()
        if binary_size is None:
            binary_size = stat.st_size
        if sha256_hash is None:
            sha256_hash = compute_file_sha256(target_file)

    # Timestamp
    dir_stat = base_dir.stat()
    mtime = dir_stat.st_mtime
    uploaded_at = metadata.get("uploaded_at")
    uploaded_ts = metadata.get("uploaded_timestamp", mtime)
    if not uploaded_at:
        uploaded_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    target_devices = metadata.get("target_devices", "*")

    return {
        "app_name": app_name,
        "version": version_folder,
        "version_string": version_str,
        "filename": binary_name or "",
        "file_size": binary_size or 0,
        "sha256": sha256_hash or "",
        "description": metadata.get("description", ""),
        "target_devices": target_devices,
        "uploaded_at": uploaded_at,
        "uploaded_timestamp": uploaded_ts,
        "folder_path": str(base_dir),
    }


def list_app_versions(app_name: str) -> list[dict[str, Any]]:
    """
    List all version folders stored in updates/<app-name>.
    Sorted according to configured strategy:
    - 'upload_time': latest uploaded version first (default)
    - 'semver': highest semantic version first
    """
    app_clean = sanitize_path_segment(app_name)
    app_dir = get_updates_dir() / app_clean

    if not app_dir.is_dir():
        return []

    config = get_config()
    strategy = getattr(config, "version_sort_strategy", "upload_time")

    versions: list[dict[str, Any]] = []
    for item in app_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            try:
                info = get_version_info(app_clean, item.name)
                versions.append(info)
            except Exception:
                continue

    if strategy == "semver":
        versions.sort(
            key=lambda v: (_parse_semver_safe(v["version_string"]), v["uploaded_timestamp"]),
            reverse=True,
        )
    else:
        # Default: upload_time / last uploaded version first
        versions.sort(
            key=lambda v: (v["uploaded_timestamp"], _parse_semver_safe(v["version_string"])),
            reverse=True,
        )

    return versions


def get_latest_version(app_name: str) -> dict[str, Any] | None:
    """
    Returns metadata for the latest version stored in updates/<app-name>.
    The server will always provide the last uploaded version of the app.
    Returns None if no versions exist.
    """
    versions = list_app_versions(app_name)
    return versions[0] if versions else None


def get_latest_version_text(app_name: str) -> str | None:
    """Returns the plain text version string for the latest version."""
    latest = get_latest_version(app_name)
    if not latest:
        return None
    return latest["version_string"]


def list_all_apps() -> list[dict[str, Any]]:
    """
    Scans the updates directory and returns summary of each app,
    including its latest version and total version count.
    """
    updates_dir = get_updates_dir()
    if not updates_dir.exists():
        updates_dir.mkdir(parents=True, exist_ok=True)
        return []

    apps_summary: list[dict[str, Any]] = []
    for item in updates_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            app_name = item.name
            versions = list_app_versions(app_name)
            latest = versions[0] if versions else None
            apps_summary.append(
                {
                    "name": app_name,
                    "latest_version": latest["version_string"] if latest else None,
                    "latest_filename": latest["filename"] if latest else None,
                    "latest_filesize": latest["file_size"] if latest else 0,
                    "versions_count": len(versions),
                    "last_uploaded_at": latest["uploaded_at"] if latest else None,
                }
            )

    apps_summary.sort(key=lambda a: a["name"].lower())
    return apps_summary


def save_new_build(
    app_name: str,
    version: str,
    filename: str,
    content: bytes,
    description: str = "",
    devices: str = "*",
) -> dict[str, Any]:
    """
    Saves a new uploaded binary build to:
    updates/<app-name>/<version>/<filename>
    and creates version.txt and metadata.json with target devices.
    """
    app_clean = sanitize_path_segment(app_name)
    version_clean = sanitize_path_segment(version)
    file_clean = sanitize_path_segment(filename)
    target_devices_clean = normalize_target_devices(devices)

    target_dir = get_updates_dir() / app_clean / version_clean
    target_dir.mkdir(parents=True, exist_ok=True)

    # Save binary file
    binary_path = target_dir / file_clean
    with open(binary_path, "wb") as fh:
        fh.write(content)

    # Compute checksum
    sha256_hash = compute_sha256(content)
    file_size = len(content)

    # Write version.txt
    version_file = target_dir / "version.txt"
    with open(version_file, "w", encoding="utf-8") as fh:
        fh.write(f"{version.strip()}\n")

    # Write metadata.json
    now = datetime.now(timezone.utc)
    metadata = {
        "app_name": app_clean,
        "version": version.strip(),
        "filename": file_clean,
        "file_size": file_size,
        "sha256": sha256_hash,
        "description": description.strip(),
        "target_devices": target_devices_clean,
        "uploaded_at": now.isoformat(),
        "uploaded_timestamp": now.timestamp(),
    }
    meta_file = target_dir / "metadata.json"
    with open(meta_file, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)

    # Touch directory mtime to match upload timestamp
    os.utime(target_dir, (now.timestamp(), now.timestamp()))

    # Sync to DB
    database.record_build(
        app_name=app_clean,
        version=version.strip(),
        filename=file_clean,
        file_size=file_size,
        sha256=sha256_hash,
        description=description.strip(),
        target_devices=target_devices_clean,
        uploaded_at=now.isoformat(),
    )

    return metadata


def rollback_build(app_name: str) -> dict[str, Any]:
    """
    Rolls back a build by removing the latest version folder.
    When the client requests next time, it provides the previous version.
    """
    app_clean = sanitize_path_segment(app_name)
    versions = list_app_versions(app_clean)

    if not versions:
        raise ValueError(f"No versions found for app '{app_name}' to roll back.")

    latest = versions[0]
    folder_to_remove = Path(latest["folder_path"])

    if folder_to_remove.exists() and folder_to_remove.is_dir():
        shutil.rmtree(folder_to_remove)

    # Delete from DB
    database.delete_build_record(app_clean, latest["version"])

    # Determine new latest version
    remaining_versions = list_app_versions(app_clean)
    new_latest = remaining_versions[0] if remaining_versions else None

    return {
        "app_name": app_clean,
        "rolled_back_version": latest["version"],
        "active_version": new_latest["version_string"] if new_latest else None,
        "remaining_versions_count": len(remaining_versions),
    }


def delete_version_folder(app_name: str, version: str) -> bool:
    """Removes a specific version folder and its DB record."""
    app_clean = sanitize_path_segment(app_name)
    version_clean = sanitize_path_segment(version)
    target_dir = get_updates_dir() / app_clean / version_clean

    if target_dir.exists() and target_dir.is_dir():
        shutil.rmtree(target_dir)
        database.delete_build_record(app_clean, version)
        return True
    return False


def get_binary_file_to_download(
    app_name: str,
    version: str | None = None,
    filename: str | None = None,
    device_id: str | None = None,
) -> tuple[Path, str, str, str]:
    """
    Finds and returns (file_path, filename, version_string, sha256) for download.
    If version is None, chooses the latest available version.
    Validates that device_id is targeted/allowed.
    """
    app_clean = sanitize_path_segment(app_name)

    if version:
        version_clean = sanitize_path_segment(version)
        version_info = get_version_info(app_clean, version_clean)
    else:
        latest = get_latest_version(app_clean)
        if not latest:
            raise FileNotFoundError(f"No build found for app '{app_name}'")
        version_info = latest

    # Check device authorization if device_id is provided
    if device_id and not is_device_allowed(version_info.get("target_devices", "*"), device_id):
        raise FileNotFoundError(
            f"Device '{device_id}' is unknown or not authorized for app '{app_name}'"
        )

    folder = Path(version_info["folder_path"])

    if filename:
        file_clean = sanitize_path_segment(filename)
        target = folder / file_clean
        if not target.is_file():
            raise FileNotFoundError(
                f"File '{filename}' not found in version '{version_info['version']}'"
            )
        sha = compute_file_sha256(target)
        return target, target.name, version_info["version_string"], sha

    # If no filename specified, use binary from version info
    if version_info["filename"]:
        target = folder / version_info["filename"]
        if target.is_file():
            return target, target.name, version_info["version_string"], version_info["sha256"]

    # Fallback search
    for item in folder.iterdir():
        if item.is_file() and item.name not in ("version.txt", "metadata.json"):
            sha = compute_file_sha256(item)
            return item, item.name, version_info["version_string"], sha

    raise FileNotFoundError(f"No binary file found in version '{version_info['version']}'")
