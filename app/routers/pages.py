"""
Page routes — server-rendered HTML views for Update Manager.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app import database
from app.core.config import get_config, get_route_path
from app.core.templating import templates
from app.services import updates as updates_svc

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    msg: str | None = Query(None),
    error: str | None = Query(None),
):
    """Home / Dashboard view."""
    config = get_config()
    apps = updates_svc.list_all_apps()
    stats = database.get_system_stats()
    recent_logs = database.get_recent_device_logs(limit=10)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": config.app_name,
            "ROUTE_PATH": get_route_path(),
            "base_url": config.base_url,
            "apps": apps,
            "stats": stats,
            "recent_logs": recent_logs,
            "msg": msg or "",
            "error": error or "",
        },
    )


@router.get("/apps/{app_name}", response_class=HTMLResponse)
async def app_details(
    request: Request,
    app_name: str,
    msg: str | None = Query(None),
    error: str | None = Query(None),
):
    """App details and version history view."""
    config = get_config()
    try:
        versions = updates_svc.list_app_versions(app_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    latest = versions[0] if versions else None

    return templates.TemplateResponse(
        request=request,
        name="app_detail.html",
        context={
            "app_name_title": app_name,
            "app_name": config.app_name,
            "ROUTE_PATH": get_route_path(),
            "base_url": config.base_url,
            "versions": versions,
            "latest": latest,
            "msg": msg or "",
            "error": error or "",
        },
    )


@router.get("/devices", response_class=HTMLResponse)
async def devices_page(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
):
    """Device activity log page."""
    config = get_config()
    logs = database.get_recent_device_logs(limit=limit)
    stats = database.get_system_stats()

    return templates.TemplateResponse(
        request=request,
        name="devices.html",
        context={
            "app_name": config.app_name,
            "ROUTE_PATH": get_route_path(),
            "base_url": config.base_url,
            "logs": logs,
            "stats": stats,
            "limit": limit,
        },
    )


@router.post("/upload")
async def web_upload_build(
    app_name: str = Form(...),
    version: str = Form(...),
    description: str = Form(""),
    devices: str = Form("*"),
    file: UploadFile = File(...),
):
    """Uploads a build from the web interface and redirects back."""
    route_path = get_route_path()
    if not file.filename:
        return RedirectResponse(
            url=f"{route_path}/?error=No+file+selected",
            status_code=303,
        )

    content = await file.read()
    if not content:
        return RedirectResponse(
            url=f"{route_path}/?error=File+cannot+be+empty",
            status_code=303,
        )

    try:
        updates_svc.save_new_build(
            app_name=app_name.strip(),
            version=version.strip(),
            filename=file.filename,
            content=content,
            description=description.strip(),
            devices=devices.strip(),
        )
        msg = f"Successfully uploaded version {version} for {app_name}!"
        return RedirectResponse(
            url=f"{route_path}/apps/{app_name.strip()}?msg={msg}",
            status_code=303,
        )
    except Exception as exc:
        return RedirectResponse(
            url=f"{route_path}/?error={exc}",
            status_code=303,
        )


@router.post("/apps/{app_name}/rollback")
async def web_rollback_app(app_name: str):
    """Rolls back the latest version via the web UI."""
    route_path = get_route_path()
    try:
        res = updates_svc.rollback_build(app_name)
        new_active = res.get("active_version") or "None"
        msg = f"Rolled back {res['rolled_back_version']}. Active version is now {new_active}."
        return RedirectResponse(
            url=f"{route_path}/apps/{app_name}?msg={msg}",
            status_code=303,
        )
    except Exception as exc:
        return RedirectResponse(
            url=f"{route_path}/apps/{app_name}?error={exc}",
            status_code=303,
        )


@router.post("/apps/{app_name}/delete-version")
async def web_delete_version(app_name: str, version: str = Form(...)):
    """Deletes a specific version via the web UI."""
    route_path = get_route_path()
    try:
        updates_svc.delete_version_folder(app_name, version)
        msg = f"Deleted version {version}."
        return RedirectResponse(
            url=f"{route_path}/apps/{app_name}?msg={msg}",
            status_code=303,
        )
    except Exception as exc:
        return RedirectResponse(
            url=f"{route_path}/apps/{app_name}?error={exc}",
            status_code=303,
        )
