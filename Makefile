.PHONY: dev test build clean lint format up down

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check app/ tests/

format:
	uv run ruff format app/ tests/

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache
