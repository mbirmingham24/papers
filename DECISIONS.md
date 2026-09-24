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
- **2026-09 — Render for the API host.** Of Render/Koyeb/Fly, only Render still has free compute; builds from the repo Dockerfile, auto-deploys after CI passes. Gave up warm starts (sleeps after 15 min idle).
- **2026-09 — AWS exercise on a new Free-plan account (open it in week 7), not a paid account + billing alarm.** Free plan can't incur charges; $100+ credits cover Fargate + ALB for weeks. Gave up: account auto-closes 6 months after signup.

## Bug log

Format: **date — symptom.** Root cause. Fix. (1–2 lines each.)

- **2026-09-23 — CI failed at "Set up job" before any step ran.** `astral-sh/setup-uv@v10` doesn't exist; that repo publishes only exact tags. Pinned `@v10.2.0`.

## Measurements

| Date | Metric | Value | Notes |
|---|---|---|---|
| | search p50 / p95 (embed only) | | |
| | search p50 / p95 (reranked) | | |
| | rerank latency torch vs. ONNX | | |
| | recall@10 embed vs. rerank vs. fine-tuned | | |
| 2026-09-23 | prod image size / idle memory | 233 MB / 42 MiB | week 0 skeleton, no ML deps yet |
| 2026-09-23 | Render cold start / warm `/health` | 13.3 s / 0.15 s | week 0 skeleton; ~17 min idle before cold request |
