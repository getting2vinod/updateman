# 📦 Update Manager

A fast, lightweight, and robust firmware & software update management server built with **FastAPI**, **uv**, **Jinja2**, and **SQLite**.

Designed for IoT devices (ESP32, Raspberry Pi, Arduino), desktop applications, mobile builds, and distributed clients to check for updates, verify checksums, download binaries, target specific devices, and seamlessly handle build rollbacks.

---

## 🌟 Key Features

- **Standardized Client Version Endpoint**:
  Remote clients check the latest available version using:
  ```http
  GET https://sasthashub.duckdns.org/updates/<device-id>/<app-name>/version.txt
  ```
  Returns the version string as plain text (e.g. `1.0.2\n`).

- **Device Targeting & Access Control**:
  - Upload builds targeted to a comma-separated list of device IDs (e.g., `esp32-node1, esp32-node2`).
  - Use `*` to target **any** device.
  - If an **unknown / unauthorized** device requests `version.txt` or attempts to download the build, the server sends a **`404 Not Found`**.

- **Folder-Per-Version Layout (Source of Truth)**:
  Builds are stored on disk under `updates/<app-name>/<version>/`:
  - The uploaded binary file (e.g., `firmware.bin`, `app.zip`, `update.bin`)
  - `version.txt` (version tag)
  - `metadata.json` (SHA256 checksum, file size, target devices, upload timestamp)

- **Instant Rollback (Filesystem-Driven)**:
  - The server always serves the last uploaded version of an application.
  - To roll back a build, simply remove the latest version folder:
    - **Via Web UI**: Click the **🔄 Rollback** button.
    - **Via REST API**: `POST /api/apps/<app-name>/rollback`.
    - **Via Shell / Filesystem**: Run `rm -rf updates/<app-name>/<latest-version>`.
  - When the client connects again, the server immediately returns the previous version.

- **Direct Binary Download Endpoints**:
  - `GET /updates/<device-id>/<app-name>/download` (downloads latest binary)
  - `GET /updates/<device-id>/<app-name>/latest` (alias)
  - `GET /updates/<device-id>/<app-name>/<version>/download` (specific version)
  - `GET /updates/<device-id>/<app-name>/<filename>` (by filename)
  - Includes `X-Version` and `X-Checksum-SHA256` HTTP headers.

- **Subpath & Reverse Proxy Friendly (`ROUTE_PATH`)**:
  - Runs at root domain (`/`) or behind reverse proxies like NGINX at any subpath (e.g., `/updates`).
  - Automatically handles path normalisation, duplicate slashes, and proxy path stripping.
  - CSS, JS, static assets, and links are dynamically rendered with `ROUTE_PATH`.

- **Audit & Check-in Logging**:
  - Every version check and download is logged to SQLite with Device ID, App Name, IP Address (respecting `X-Forwarded-For`), User-Agent, and timestamp.
  - Search and view logs in the web dashboard or via API.

---

## 📁 Directory Structure

```text
UpdateManager/
├── app/
│   ├── core/
│   │   ├── config.py            # AppConfig dataclass, JSON loader, path constants
│   │   ├── middleware.py        # NormalizePathMiddleware (path & subpath normalization)
│   │   └── templating.py       # Jinja2 template setup, context processors & static_url
│   ├── models/
│   │   └── build.py             # Pydantic models for OpenAPI schemas
│   ├── routers/
│   │   ├── api.py               # REST API (/api/upload, /api/apps, /api/rollback)
│   │   ├── pages.py             # Server-rendered HTML dashboard & views
│   │   └── updates.py           # Client update routes (/updates/...)
│   ├── services/
│   │   └── updates.py           # File scanning, sorting, upload, rollback & device checks
│   ├── static/
│   │   ├── css/style.css        # Responsive dashboard styling
│   │   └── js/main.js           # Clipboard copy & client scripts
│   ├── templates/
│   │   ├── base.html            # Base layout with navbar, alerts & footer
│   │   ├── index.html           # Main dashboard, stats & upload form
│   │   ├── app_detail.html      # App version history, device target badges & snippets
│   │   └── devices.html         # Device activity audit table
│   ├── database.py              # SQLite storage for apps, builds, and device logs
│   └── main.py                  # FastAPI application entry point & static mounting
├── config/
│   └── settings.json            # Application settings (base URL, storage directory)
├── data/
│   └── app.db                   # SQLite database (auto-generated)
├── updates/                     # Storage root for builds (source of truth)
│   └── <app-name>/
│       ├── <version-1>/
│       └── <version-2>/
├── tests/
│   ├── test_updates.py          # Client version check, download & device targeting tests
│   ├── test_api.py              # API upload, list, delete & validation tests
│   └── test_pages.py            # Web UI & static asset rendering tests
├── Dockerfile                   # Production container with health check
├── docker-compose.yaml          # Container setup with port 4016 and volumes
└── pyproject.toml               # Dependencies and tool configurations
```

---

## 🚀 Quick Start

### 1. Run with Docker Compose (Recommended)

```bash
docker compose up -d
```

- Accessible locally at: `http://localhost:4016/` (or via reverse proxy at `/updates`).
- Containers use port **4016**.
- Persistent directories are mounted to `./data` (database) and `./updates` (builds).
- Live reload is enabled for the `./app` directory.

To stop or restart:
```bash
# Restart after config change
docker compose restart

# Stop container
docker compose down
```

### 2. Run Locally with `uv`

```bash
# 1. Install dependencies
uv sync

# 2. Start development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 4016
```

Open your browser at `http://localhost:4016/`.

### 3. Run Test Suite

```bash
uv run pytest -v
```

---

## 📡 Remote Client Endpoints

### 1. Check Latest Version

```http
GET https://sasthashub.duckdns.org/updates/<device-id>/<app-name>/version.txt
```

- **Authorized Device (or `*` target)**:
  - **Status**: `200 OK` (`text/plain; charset=utf-8`)
  - **Body**: `1.0.2\n`
- **Unknown Device**:
  - **Status**: `404 Not Found`
  - **Body**: `Device '<device-id>' is unknown or not authorized for app '<app-name>'`

### 2. Download Latest Binary

```http
GET https://sasthashub.duckdns.org/updates/<device-id>/<app-name>/download
```

- **Status**: `200 OK` (`application/octet-stream`)
- **Headers**:
  - `X-Version`: `1.0.2`
  - `X-Checksum-SHA256`: `d4735e3a265e16eee03f59718b9b5d03019c07d8b6c51f90da3a666eec13ab35`
  - `Content-Disposition`: `attachment; filename="firmware.bin"`

### 3. Download Specific Version / Filename

- Specific version: `GET /updates/<device-id>/<app-name>/<version>/download`
- Specific file: `GET /updates/<device-id>/<app-name>/<filename>`

---

## 🔄 Rollback Mechanism

The server always supplies the **last uploaded version** of an application.

When a build needs to be rolled back:
1. **Via Web Dashboard**: Click the **🔄 Rollback** button next to the app on the Dashboard or on the App Detail page.
2. **Via REST API**:
   ```bash
   curl -X POST https://sasthashub.duckdns.org/api/apps/<app-name>/rollback
   ```
3. **Directly on Filesystem**:
   ```bash
   rm -rf updates/<app-name>/<latest-version>
   ```

Because the server inspects the filesystem directly on each check, deleting the latest version folder immediately activates the previous version. The next time the client queries `version.txt`, it receives the previous version and executes its downgrade.

---

## 💻 Client Integration Examples

### Bash / Curl Script

```bash
#!/usr/bin/env bash
set -e

DEVICE_ID="rpi-sensor-01"
APP_NAME="sensor-daemon"
SERVER="https://sasthashub.duckdns.org"
CURRENT_VERSION="1.0.0"

# Check latest version
LATEST=$(curl -sf "$SERVER/updates/$DEVICE_ID/$APP_NAME/version.txt" | tr -d '\r\n')

if [ -z "$LATEST" ]; then
    echo "No update found or device not authorized (404)."
    exit 1
fi

echo "Current version: $CURRENT_VERSION | Available: $LATEST"

if [ "$LATEST" != "$CURRENT_VERSION" ]; then
    echo "Updating to version $LATEST..."
    curl -fL -o "$APP_NAME.bin" "$SERVER/updates/$DEVICE_ID/$APP_NAME/download"
    chmod +x "$APP_NAME.bin"
    echo "Update downloaded successfully."
fi
```

### Python Client

```python
import httpx

DEVICE_ID = "desktop-client-01"
APP_NAME = "my-desktop-app"
SERVER = "https://sasthashub.duckdns.org"
CURRENT_VERSION = "1.0.0"

# 1. Query latest version
resp = httpx.get(f"{SERVER}/updates/{DEVICE_ID}/{APP_NAME}/version.txt")

if resp.status_code == 200:
    latest_version = resp.text.strip()
    if latest_version != CURRENT_VERSION:
        print(f"New version {latest_version} available. Downloading...")
        download_resp = httpx.get(f"{SERVER}/updates/{DEVICE_ID}/{APP_NAME}/download")
        sha256 = download_resp.headers.get("X-Checksum-SHA256")
        
        with open("update.bin", "wb") as fh:
            fh.write(download_resp.content)
        print(f"Downloaded build. SHA256: {sha256}")
elif resp.status_code == 404:
    print("Device is unknown or no updates found.")
```

### ESP32 (Arduino C++)

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <Update.h>

const char* deviceId = "esp32-living-room";
const char* appName = "smart-thermostat";
const char* currentVersion = "1.0.0";
const char* serverUrl = "https://sasthashub.duckdns.org";

void checkForUpdates() {
    HTTPClient http;
    String versionUrl = String(serverUrl) + "/updates/" + deviceId + "/" + appName + "/version.txt";
    http.begin(versionUrl);
    int httpCode = http.GET();

    if (httpCode == HTTP_CODE_OK) {
        String newVersion = http.getString();
        newVersion.trim();

        if (newVersion != currentVersion) {
            Serial.printf("New version found: %s. Starting OTA...\n", newVersion.c_str());
            String downloadUrl = String(serverUrl) + "/updates/" + deviceId + "/" + appName + "/download";
            // Perform OTA flash using downloadUrl
        }
    } else if (httpCode == 404) {
        Serial.println("Device not targeted or no updates found.");
    }
    http.end();
}
```

---

## 🛠️ REST API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/upload` | `POST` | Upload a binary build (`multipart/form-data`) |
| `/api/apps` | `GET` | List all apps, latest versions, and build stats |
| `/api/apps/{app}` | `GET` | Get version history and metadata for an app |
| `/api/apps/{app}/rollback` | `POST` | Remove latest build folder and activate previous version |
| `/api/apps/{app}/{version}` | `DELETE` | Delete a specific version folder |
| `/api/devices` | `GET` | Get recent device check-in audit logs |
| `/api/health` | `GET` | Health check endpoint |
| `/api/info` | `GET` | Application runtime metadata |

### Upload Build via `curl` (CI/CD Pipelines)

```bash
curl -X POST https://sasthashub.duckdns.org/api/upload \
  -F "app_name=smart-sensor" \
  -F "version=1.0.2" \
  -F "devices=esp32-01, esp32-02" \
  -F "description=Fixed WiFi reconnect bug" \
  -F "file=@build/firmware.bin"
```

*(Pass `devices=*` to target all devices).*

---

## ⚙️ Configuration

### `config/settings.json`

```json
{
  "app_name": "Update Manager",
  "version": "1.0.0",
  "debug": false,
  "base_url": "https://sasthashub.duckdns.org",
  "updates_dir": "updates",
  "version_sort_strategy": "upload_time",
  "features": {
    "enable_device_logging": true
  }
}
```

- `base_url`: Domain displayed in client instructions and copyable links.
- `updates_dir`: Directory for storing binary builds (relative to project root, or absolute).
- `version_sort_strategy`: `"upload_time"` (last uploaded version is latest) or `"semver"` (semantic version order).

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `ROUTE_PATH` | Subpath prefix when running behind a reverse proxy (e.g. `updates` or `/updates`) | `""` (root) |
| `UPDATES_DIR` | Override path for the build updates directory | `updates/` |
| `CONFIG_PATH` | Override settings file path (e.g. for testing) | `config/settings.json` |
| `PORT` | Web server port | `4016` |
| `HOST` | Bind host address | `0.0.0.0` |
