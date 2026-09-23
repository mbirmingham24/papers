# CLAUDE.md

Context for Claude Code in this repo. Read `DESIGN.md` before starting any task. Check `DECISIONS.md` before proposing a change to a decision already made.

## What this is

Semantic search over recent arXiv papers. A query is embedded, candidates come from pgvector, a cross-encoder reranks them, and my feedback (relevant / not) is used to fine-tune the reranker. Single user, personal tool.

## The point of this project

This is a **learning project**. I'm using it to learn full-stack development and deployment properly, not to ship as fast as possible. I have to defend every part of it in interviews, so code I can't explain is worth nothing to me.

In this repo:

1. **Design before code.** When starting a new component, ask what approach I have in mind, or propose one in a few lines and wait for agreement. Don't jump straight to implementation.
2. **Small diffs.** One concern per change. Never build a whole feature in one pass.
3. **Explain the non-obvious.** For anything not self-explanatory (async, SQL and indexes, Docker layering, CORS, env/config), give a short explanation in chat. Don't bury it in code comments.
4. **Debugging: hints first.** When something breaks, help me diagnose with questions and pointers before handing me the fix. If I say "just fix it," fix it.
5. **Tests ship with features.** Backend logic changes come with a test in the same change.
6. **Log what broke.** After a real bug is fixed, suggest a one-to-two line entry for `DECISIONS.md` → Bug log.

## Stack

- **Frontend:** TypeScript, React, Vite, TanStack Query, Tailwind. Not Next.js (deliberate).
- **Backend:** Python 3.12, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2.0, Alembic.
- **Data:** PostgreSQL 16 + pgvector (HNSW). Redis for query-embedding cache and RQ broker.
- **Jobs:** RQ (not Celery).
- **ML:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim embeddings), `cross-encoder/ms-marco-MiniLM-L-6-v2` (rerank). PyTorch for fine-tuning **locally only**. **Serving uses ONNX Runtime; the production image must not include PyTorch.**
- **Quality:** pytest, pytest-asyncio, Vitest, ruff, eslint, pre-commit, GitHub Actions.
- **Infra:** Docker (multi-stage), docker-compose for local dev. Free-tier hosts in prod (see `DESIGN.md` → Deployment).

## Hard constraints

- **Zero recurring cost.** Free tiers only. Never create, or suggest creating, a paid cloud resource without my explicit confirmation. The one AWS exercise (week 7) is deploy-and-tear-down the same day.
- Production runs on **CPU with ~512 MB RAM**. Keep the serving image and memory footprint small.
- Fine-tuning and bulk embedding run **locally**, never on the free host.

## Non-goals (push back if a change drifts here)

No auth, no multi-user, no pagination, no Kubernetes, no Spark, no Next.js, no services beyond API + worker.

## Conventions

- Backend: `backend/app/{api,models,schemas,services,jobs,ml,core}`, tests in `backend/tests`.
- Frontend: `frontend/src/{components,hooks,api,pages}`.
- All schema changes go through Alembic. Never alter tables by hand.
- Config via env vars loaded with pydantic-settings. No secrets in the repo; `.env.example` lists every variable.
- Type hints everywhere in Python; `strict: true` in `tsconfig`.
- Commit small and often, terse messages ("add feedback table", "fix embed cache key"). Commit before anything risky.

## Commands

Fill in as they come to exist.

```
make up        # docker-compose up: api, worker, postgres, redis
make down
make migrate   # alembic upgrade head
make test      # backend + frontend tests
make lint      # ruff + eslint
make ingest    # run ingest job locally
```
