"""
Client Update Routes — Serving version info and binary files to remote devices.
Matches specification:
  https://sasthashub.duckdns.org/updates/<device-id>/<app-name>/version.txt
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse

from app import database
from app.services import updates as updates_svc

router = APIRouter(tags=["client-updates"])


def _extract_ip(request: Request) -> str:
    """Extract client IP, taking X-Forwarded-For into account."""
    x_fwd = request.headers.get("x-forwarded-for")
    if x_fwd:
        return x_fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


# ---------------------------------------------------------------------------
# Version Check Endpoints
# ---------------------------------------------------------------------------


@router.get("/updates/{device_id}/{app_name}/version.txt", response_class=PlainTextResponse)
@router.get("/{device_id}/{app_name}/version.txt", response_class=PlainTextResponse)
async def check_version_device(device_id: str, app_name: str, request: Request):
    """
    Checks the latest version stored for the app in updates/<app-name>.
    Returns the version string as plain text if device is targeted.
    If unknown device, sends a 404.
    Logs the device check-in.
    """
    try:
        latest = updates_svc.get_latest_version(app_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not latest:
        raise HTTPException(
            status_code=404,
            detail=f"No updates found for app '{app_name}'",
        )

    # Check device targeting
    target_devices = latest.get("target_devices", "*")
    if not updates_svc.is_device_allowed(target_devices, device_id):
        database.log_device_event(
            device_id=device_id,
            app_name=app_name,
            action="rejected_unknown_device",
            version_served="none",
            ip_address=_extract_ip(request),
            user_agent=request.headers.get("user-agent", ""),
        )
        raise HTTPException(
            status_code=404,
            detail=f"Device '{device_id}' is unknown or not authorized for app '{app_name}'",
        )

    version_str = latest["version_string"]

    # Log device check-in
    database.log_device_event(
        device_id=device_id,
        app_name=app_name,
        action="check_version",
        version_served=version_str,
        ip_address=_extract_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )

    return PlainTextResponse(f"{version_str}\n", media_type="text/plain; charset=utf-8")


@router.get("/updates/{app_name}/version.txt", response_class=PlainTextResponse)
@router.get("/{app_name}/version.txt", response_class=PlainTextResponse)
async def check_version_direct(app_name: str, request: Request):
    """Direct version check without device-id."""
    return await check_version_device(
        device_id="anonymous",
        app_name=app_name,
        request=request,
    )


# ---------------------------------------------------------------------------
# Binary Download Endpoints (with device_id)
# ---------------------------------------------------------------------------


@router.get("/updates/{device_id}/{app_name}/download")
@router.get("/updates/{device_id}/{app_name}/latest")
@router.get("/{device_id}/{app_name}/download")
@router.get("/{device_id}/{app_name}/latest")
async def download_latest_binary(device_id: str, app_name: str, request: Request):
    """Download the latest binary build for the app."""
    try:
        file_path, filename, version_str, sha256 = updates_svc.get_binary_file_to_download(
            app_name=app_name,
            device_id=device_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    database.log_device_event(
        device_id=device_id,
        app_name=app_name,
        action="download_binary",
        version_served=version_str,
        ip_address=_extract_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
        headers={
            "X-Version": version_str,
            "X-Checksum-SHA256": sha256,
        },
    )


@router.get("/updates/{device_id}/{app_name}/{version}/download")
@router.get("/{device_id}/{app_name}/{version}/download")
async def download_specific_version_binary(
    device_id: str,
    app_name: str,
    version: str,
    request: Request,
):
    """Download the binary file for a specific version."""
    try:
        file_path, filename, version_str, sha256 = updates_svc.get_binary_file_to_download(
            app_name=app_name,
            version=version,
            device_id=device_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    database.log_device_event(
        device_id=device_id,
        app_name=app_name,
        action="download_binary_version",
        version_served=version_str,
        ip_address=_extract_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
        headers={
            "X-Version": version_str,
            "X-Checksum-SHA256": sha256,
        },
    )


@router.get("/updates/{device_id}/{app_name}/{version}/{filename}")
@router.get("/{device_id}/{app_name}/{version}/{filename}")
async def download_specific_version_file(
    device_id: str,
    app_name: str,
    version: str,
    filename: str,
    request: Request,
):
    """Download a specific named file inside a version folder."""
    try:
        file_path, actual_filename, version_str, sha256 = updates_svc.get_binary_file_to_download(
            app_name=app_name,
            version=version,
            filename=filename,
            device_id=device_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    database.log_device_event(
        device_id=device_id,
        app_name=app_name,
        action="download_file",
        version_served=version_str,
        ip_address=_extract_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )

    return FileResponse(
        path=str(file_path),
        filename=actual_filename,
        media_type="application/octet-stream",
        headers={
            "X-Version": version_str,
            "X-Checksum-SHA256": sha256,
        },
    )


@router.get("/updates/{device_id}/{app_name}/{filename}")
@router.get("/{device_id}/{app_name}/{filename}")
async def download_named_file_latest(
    device_id: str,
    app_name: str,
    filename: str,
    request: Request,
):
    """Download a specific named file from the latest version."""
    if filename in ("download", "latest"):
        return await download_latest_binary(device_id, app_name, request)

    try:
        file_path, actual_filename, version_str, sha256 = updates_svc.get_binary_file_to_download(
            app_name=app_name,
            filename=filename,
            device_id=device_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    database.log_device_event(
        device_id=device_id,
        app_name=app_name,
        action="download_file",
        version_served=version_str,
        ip_address=_extract_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )

    return FileResponse(
        path=str(file_path),
        filename=actual_filename,
        media_type="application/octet-stream",
        headers={
            "X-Version": version_str,
            "X-Checksum-SHA256": sha256,
        },
    )


# ---------------------------------------------------------------------------
# Binary Download Endpoints (without device_id)
# ---------------------------------------------------------------------------


@router.get("/updates/{app_name}/download")
@router.get("/updates/{app_name}/latest")
@router.get("/{app_name}/download")
@router.get("/{app_name}/latest")
async def download_latest_binary_direct(app_name: str, request: Request):
    """Direct binary download without device-id."""
    return await download_latest_binary("anonymous", app_name, request)


@router.get("/updates/{app_name}/{version}/download")
@router.get("/{app_name}/{version}/download")
async def download_specific_version_binary_direct(app_name: str, version: str, request: Request):
    """Direct specific version binary download without device-id."""
    return await download_specific_version_binary("anonymous", app_name, version, request)
