.PHONY: up down logs migrate test

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	uv run --directory backend alembic upgrade head

test:
	uv run --directory backend pytest
