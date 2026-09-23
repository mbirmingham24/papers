# DECISIONS.md

Two logs. Keep entries short. This file is the source for interview answers and resume bullets.

## Decisions

Format: **date — decision.** Why. What I gave up.

- **2026-09 — React + Vite, not Next.js.** Want the client/server boundary explicit while learning. Gave up SSR and file routing.
- **2026-09 — pgvector, not a separate vector DB.** One database to operate; learn indexing in Postgres. Gave up some ANN tuning options.
- **2026-09 — RQ, not Celery.** Enough for three job types with far less config. Gave up scheduling and routing features.
- **2026-09 — ONNX Runtime for serving, PyTorch only for training.** Free host has ~512 MB RAM; torch alone blows that. Gave up a single codepath for train and serve.
- **2026-09 — Free-tier hosting + GitHub Actions for scheduled ingest.** Zero recurring cost. Gave up an always-on worker in prod.
- **2026-09 — uv for Python packaging.** Fast, lockfile (`uv.lock`) for reproducible installs, caches well in Docker layers. Gave up the familiarity of plain pip/requirements.txt.
- **2026-09 — `/health` is liveness-only in week 0; DB/Redis checks added in week 1.** Lets the first deploy ship before Neon/Upstash exist. Gave up (temporarily) a health check that catches dependency outages.

## Bug log

Format: **date — symptom.** Root cause. Fix. (1–2 lines each.)

-

## Measurements

| Date | Metric | Value | Notes |
|---|---|---|---|
| | search p50 / p95 (embed only) | | |
| | search p50 / p95 (reranked) | | |
| | rerank latency torch vs. ONNX | | |
| | recall@10 embed vs. rerank vs. fine-tuned | | |
| | prod image size / idle memory | | |
