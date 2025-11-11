.PHONY: help install setup-db dev test clean docker-up docker-down migrate

help:
	@echo "Available commands:"
	@echo "  make install     - Install dependencies"
	@echo "  make setup-db    - Setup database and run migrations"
	@echo "  make dev         - Run development server"
	@echo "  make test        - Run tests"
	@echo "  make clean       - Clean temporary files"
	@echo "  make docker-up   - Start Docker services"
	@echo "  make docker-down - Stop Docker services"
	@echo "  make migrate     - Create new migration"

install:
	poetry install
	poetry run playwright install chromium

setup-db:
	poetry run alembic upgrade head

dev:
	poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	poetry run pytest -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true

docker-up:
	docker-compose up --build -d

docker-down:
	docker-compose down

migrate:
	poetry run alembic revision --autogenerate -m "$(MSG)"
