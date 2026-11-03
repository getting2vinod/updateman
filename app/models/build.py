"""Pydantic models for Update Manager API."""

from __future__ import annotations

from pydantic import BaseModel


class BuildMetadata(BaseModel):
    """Metadata for an uploaded build."""

    app_name: str
    version: str
    filename: str
    file_size: int
    sha256: str
    description: str | None = ""
    target_devices: str | None = "*"
    uploaded_at: str
    uploaded_timestamp: float


class AppSummary(BaseModel):
    """Summary of an application and its latest build."""

    name: str
    latest_version: str | None = None
    latest_filename: str | None = None
    latest_filesize: int = 0
    versions_count: int = 0
    last_uploaded_at: str | None = None


class RollbackResponse(BaseModel):
    """Response returned after rolling back a build."""

    app_name: str
    rolled_back_version: str
    active_version: str | None = None
    remaining_versions_count: int


class DeviceLogEntry(BaseModel):
    """Log entry for device update polling / download."""

    id: int
    device_id: str
    app_name: str
    action: str
    version_served: str
    ip_address: str | None = ""
    user_agent: str | None = ""
    created_at: str
