.PHONY: setup up down serve seed test lint check

setup:
	uv sync --locked
up:
	docker compose up -d --wait elasticsearch
down:
	docker compose down
serve:
	uv run --locked uvicorn wikinews_ir.api.main:app --reload
seed:
	uv run --locked wikinews-ir seed-demo
test:
	uv run --locked pytest -q
lint:
	uv run --locked ruff check .
check: lint test
