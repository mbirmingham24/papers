.PHONY: up down logs migrate test ingest

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

# make ingest CATEGORY=cs.CL DAYS=30
CATEGORY ?= cs.LG
DAYS ?= 7

ingest:
	uv run --directory backend python -m app.jobs.ingest $(CATEGORY) --days $(DAYS)
