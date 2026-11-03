FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

# Install ca-certificates and curl for uv installer
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Install dependencies using uv sync
COPY pyproject.toml ./
RUN uv sync --no-dev

# Copy application and configuration files
COPY app ./app
COPY config ./config

# Ensure persistent directories exist
RUN mkdir -p /app/data /app/config /app/updates

EXPOSE 4016

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:4016/api/health')" || exit 1

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4016"]
