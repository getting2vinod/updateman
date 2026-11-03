"""
API routes — JSON endpoints for build uploads, rollback, app management, and metrics.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from app import database
from app.core.config import get_config, get_route_path
from app.services import updates as updates_svc

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def health_check():
    """Health check endpoint for Docker / orchestration."""
    return JSONResponse(
        {
            "status": "healthy",
            "route_path": get_route_path(),
            "timestamp": datetime.now().isoformat(),
        }
    )


@router.get("/info")
async def info_endpoint():
    """Returns application runtime metadata."""
    config = get_config()
    stats = database.get_system_stats()
    return JSONResponse(
        {
            "app_name": config.app_name,
            "version": config.version,
            "base_url": config.base_url,
            "route_path": get_route_path(),
            "stats": stats,
            "database_connected": True,
        }
    )


@router.post("/upload")
async def upload_build(
    app_name: str = Form(..., description="Application name (e.g. 'my-app' or 'sensor-firmware')"),
    version: str = Form(..., description="Build version string (e.g. '1.0.0' or '2.1.3-beta')"),
    description: str = Form("", description="Release notes / build description"),
    devices: str = Form("*", description="Comma-separated list of target device IDs, or * for all"),
    file: UploadFile = File(..., description="Binary / build file"),
):
    """
    Upload a binary or build file for an application.
    Creates updates/<app-name>/<version>/ with the binary, version.txt, and metadata.json.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file cannot be empty.")

    try:
        metadata = updates_svc.save_new_build(
            app_name=app_name,
            version=version,
            filename=file.filename,
            content=content,
            description=description,
            devices=devices,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save build: {exc}") from exc

    return JSONResponse(
        {
            "status": "success",
            "message": f"Successfully uploaded {file.filename} (version {version}) for app '{app_name}'",
            "data": metadata,
        },
        status_code=201,
    )


@router.get("/apps")
async def list_apps():
    """List all applications and summary of latest builds."""
    apps = updates_svc.list_all_apps()
    return JSONResponse({"apps": apps, "total": len(apps)})


@router.get("/apps/{app_name}")
async def get_app_details(app_name: str):
    """Get all versions and details for a specific app."""
    try:
        versions = updates_svc.list_app_versions(app_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not versions:
        raise HTTPException(status_code=404, detail=f"App '{app_name}' not found.")

    return JSONResponse(
        {
            "app_name": app_name,
            "latest_version": versions[0]["version_string"] if versions else None,
            "total_versions": len(versions),
            "versions": versions,
        }
    )


@router.post("/apps/{app_name}/rollback")
async def rollback_app(app_name: str):
    """
    Rolls back the app build by removing its latest version folder.
    Subsequent client requests will receive the previous version.
    """
    try:
        result = updates_svc.rollback_build(app_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {exc}") from exc

    return JSONResponse(
        {
            "status": "success",
            "message": (
                f"Rolled back build '{result['rolled_back_version']}'. "
                + (
                    f"Current active version is now '{result['active_version']}'."
                    if result["active_version"]
                    else "No versions remaining."
                )
            ),
            "data": result,
        }
    )


@router.delete("/apps/{app_name}/{version}")
async def delete_version(app_name: str, version: str):
    """Delete a specific version folder and its build record."""
    try:
        success = updates_svc.delete_version_folder(app_name, version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not success:
        raise HTTPException(
            status_code=404, detail=f"Version '{version}' for app '{app_name}' not found."
        )

    return JSONResponse(
        {
            "status": "success",
            "message": f"Successfully deleted version '{version}' of '{app_name}'.",
        }
    )


@router.get("/devices")
async def get_devices(limit: int = Query(50, ge=1, le=500)):
    """Returns recent device check-in logs."""
    logs = database.get_recent_device_logs(limit=limit)
    return JSONResponse({"logs": logs, "total": len(logs)})
