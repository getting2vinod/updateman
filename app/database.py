"""SQLite database connection, schema initialization, and CRUD helpers for Update Manager."""

import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.core.config import DATA_DIR

DB_PATH = DATA_DIR / "app.db"


def get_db() -> sqlite3.Connection:
    """Returns a SQLite database connection with Row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initializes the database schema for Update Manager."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        cursor = conn.cursor()

        # Apps table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS apps (
                name TEXT PRIMARY KEY,
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Builds table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS builds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_name TEXT NOT NULL,
                version TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                description TEXT DEFAULT '',
                target_devices TEXT DEFAULT '*',
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(app_name, version)
            );
        """)

        # Migration: ensure target_devices column exists for existing DBs
        cursor.execute("PRAGMA table_info(builds);")
        columns = [row[1] for row in cursor.fetchall()]
        if "target_devices" not in columns:
            cursor.execute("ALTER TABLE builds ADD COLUMN target_devices TEXT DEFAULT '*';")

        # Device logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                app_name TEXT NOT NULL,
                action TEXT NOT NULL,
                version_served TEXT NOT NULL,
                ip_address TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Indices for fast queries
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_device_logs_device ON device_logs(device_id);"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_device_logs_app ON device_logs(app_name);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_device_logs_time ON device_logs(created_at DESC);"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_builds_app ON builds(app_name);")

        conn.commit()


# ---------------------------------------------------------------------------
# App CRUD
# ---------------------------------------------------------------------------


def upsert_app(name: str, description: str = "") -> None:
    """Inserts or updates an app entry."""
    with get_db() as conn:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO apps (name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description = CASE WHEN excluded.description != '' THEN excluded.description ELSE apps.description END,
                updated_at = excluded.updated_at;
        """,
            (name, description, now, now),
        )
        conn.commit()


def get_all_apps_db() -> list[dict[str, Any]]:
    """Returns all registered apps from DB."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, description, created_at, updated_at FROM apps ORDER BY name ASC;"
        )
        return [dict(row) for row in cursor.fetchall()]


def delete_app_db(name: str) -> bool:
    """Deletes an app and its build records from DB."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM builds WHERE app_name = ?;", (name,))
        cursor.execute("DELETE FROM apps WHERE name = ?;", (name,))
        conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Build CRUD
# ---------------------------------------------------------------------------


def record_build(
    app_name: str,
    version: str,
    filename: str,
    file_size: int,
    sha256: str,
    description: str = "",
    target_devices: str = "*",
    uploaded_at: str | None = None,
) -> int:
    """Records a new build or updates existing."""
    if not uploaded_at:
        uploaded_at = datetime.now(timezone.utc).isoformat()

    upsert_app(app_name)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO builds (app_name, version, filename, file_size, sha256, description, target_devices, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(app_name, version) DO UPDATE SET
                filename = excluded.filename,
                file_size = excluded.file_size,
                sha256 = excluded.sha256,
                description = excluded.description,
                target_devices = excluded.target_devices,
                uploaded_at = excluded.uploaded_at;
        """,
            (
                app_name,
                version,
                filename,
                file_size,
                sha256,
                description,
                target_devices,
                uploaded_at,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0


def delete_build_record(app_name: str, version: str) -> bool:
    """Removes a build record from DB."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM builds WHERE app_name = ? AND version = ?;", (app_name, version)
        )
        conn.commit()
        return cursor.rowcount > 0


def get_build_record(app_name: str, version: str) -> dict[str, Any] | None:
    """Returns DB record for a build if exists."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM builds WHERE app_name = ? AND version = ?;",
            (app_name, version),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Device Logging
# ---------------------------------------------------------------------------


def log_device_event(
    device_id: str,
    app_name: str,
    action: str,
    version_served: str,
    ip_address: str = "",
    user_agent: str = "",
) -> None:
    """Logs a device request (version check or download)."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO device_logs (device_id, app_name, action, version_served, ip_address, user_agent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
            (device_id, app_name, action, version_served, ip_address, user_agent, now),
        )
        conn.commit()


def get_recent_device_logs(limit: int = 50) -> list[dict[str, Any]]:
    """Returns recent device activity logs."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, device_id, app_name, action, version_served, ip_address, user_agent, created_at
            FROM device_logs
            ORDER BY id DESC
            LIMIT ?;
        """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_system_stats() -> dict[str, Any]:
    """Returns summary stats for the dashboard."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT name) FROM apps;")
        app_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM builds;")
        build_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT device_id) FROM device_logs;")
        device_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM device_logs;")
        total_requests = cursor.fetchone()[0]

        return {
            "app_count": app_count,
            "build_count": build_count,
            "device_count": device_count,
            "total_requests": total_requests,
        }
