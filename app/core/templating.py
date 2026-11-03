"""
Jinja2 template configuration.

Creates a pre-configured :class:`~fastapi.templating.Jinja2Templates`
instance with the ``ROUTE_PATH`` global, context processor, and filters.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.core.config import TEMPLATES_DIR, get_route_path


def format_datetime(value: str | None) -> str:
    """Jinja filter to format ISO datetime strings as ``dd-mm-YYYY HH:MM``."""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).strip().replace(" ", "T"))
        return dt.strftime("%d-%m-%Y %H:%M")
    except Exception:
        return str(value)


def static_url(path: str) -> str:
    """Generate route_path-prefixed static file URL.

    Example: ``static_url('css/style.css')`` -> ``/updates/static/css/style.css``
    """
    rp = get_route_path()
    clean_path = path.lstrip("/")
    return f"{rp}/static/{clean_path}"


def _route_path_context(request: Request) -> dict[str, Any]:
    """Context processor that ensures ROUTE_PATH is always available in templates."""
    rp = get_route_path()
    return {
        "ROUTE_PATH": rp,
        "route_path": rp,
        "static_url": static_url,
    }


def _create_templates() -> Jinja2Templates:
    """Build and return a configured :class:`Jinja2Templates` instance."""
    tpl = Jinja2Templates(
        directory=TEMPLATES_DIR,
        context_processors=[_route_path_context],
    )
    tpl.env.globals["get_route_path"] = get_route_path
    tpl.env.globals["ROUTE_PATH"] = get_route_path()
    tpl.env.globals["static_url"] = static_url
    tpl.env.filters["datetime_fmt"] = format_datetime
    tpl.env.filters["static_url"] = static_url
    return tpl


templates: Jinja2Templates = _create_templates()
