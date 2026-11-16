.PHONY: setup up down serve seed test lint check

setup:
	uv lock
	uv sync
up:
	docker compose up -d elasticsearch
down:
	docker compose down
serve:
	uv run uvicorn wikinews_ir.api.main:app --reload
seed:
	uv run wikinews-ir seed-demo
test:
	uv run pytest -q
lint:
	uv run ruff check .
check: lint test
