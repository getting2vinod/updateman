"""FastAPI Application — Entry Point for Update Manager."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import database
from app.core.config import STATIC_DIR, get_config, get_route_path, get_updates_dir
from app.core.middleware import NormalizePathMiddleware
from app.core.templating import templates  # noqa: F401 — imported for side-effect (filter registration)
from app.routers import api, pages, updates


def create_app() -> FastAPI:
    """Application factory: creates and configures the FastAPI instance."""
    config = get_config()

    application = FastAPI(
        title=config.app_name,
        version=config.version,
        debug=config.debug,
    )

    # Middleware
    application.add_middleware(NormalizePathMiddleware)

    # Database
    database.init_db()

    # Ensure updates storage directory exists
    updates_dir = get_updates_dir()
    updates_dir.mkdir(parents=True, exist_ok=True)

    # Static files
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    route_path = get_route_path()
    if route_path:
        application.mount(
            f"{route_path}/static", StaticFiles(directory=STATIC_DIR), name="static_prefixed"
        )
    route_path = get_route_path()
    if route_path:
        application.mount(f"{route_path}/static", StaticFiles(directory=STATIC_DIR), name="static_prefixed")

    # Routers
    application.include_router(updates.router)
    application.include_router(pages.router)
    application.include_router(api.router)

    return application


app = create_app()
