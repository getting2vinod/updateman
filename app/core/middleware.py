"""
ASGI middleware for path normalisation.

* Collapses duplicate slashes (``//`` → ``/``).
* Collapses repeated ``ROUTE_PATH`` prefixes.
* Strips the ``ROUTE_PATH`` prefix so internal routing works at ``/``.
"""

from __future__ import annotations

import re

from app.core.config import get_route_path


class NormalizePathMiddleware:
    """ASGI middleware that normalises request paths.

    Handles:
    1. Collapsing multiple consecutive slashes (e.g. ``//`` or ``///`` → ``/``).
    2. Collapsing repeated ``ROUTE_PATH`` occurrences
       (e.g. ``/task/task/…`` → ``/task/…``).
    3. Normalising request paths so endpoints declared at ``/`` match
       regardless of whether the reverse proxy strips the ``ROUTE_PATH``
       prefix or forwards it.
    """

    def __init__(self, app_instance):
        self.app = app_instance

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path: str = scope.get("path", "")
            route_path: str = get_route_path()

            # 1. Collapse multiple consecutive slashes
            path = re.sub(r"/{2,}", "/", path)

            # 2. Collapse repeated ROUTE_PATH prefixes if ROUTE_PATH is set
            if route_path:
                repeated_pattern = rf"^({re.escape(route_path)})+"
                path = re.sub(repeated_pattern, route_path, path)

                # 3. Strip ROUTE_PATH prefix for internal routing
                if path == route_path:
                    path = "/"
                elif path.startswith(route_path + "/"):
                    path = path[len(route_path) :]

            scope["path"] = path

        await self.app(scope, receive, send)


# Backward-compatible alias
RemoveDoubleSlashesMiddleware = NormalizePathMiddleware
