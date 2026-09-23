# arXiv Semantic Search: Design

## 1. Goals

**Product:** type a question, get the 10 most relevant recent arXiv papers in under half a second, and have ranking improve as I mark results relevant or not.

**Learning (the real point):**
- Own a full-stack app end to end, from empty repo to deployed
- Serve a model behind an API under a real latency and memory budget
- Use Postgres as more than storage (vector search, indexes, migrations)
- Run background jobs with retries and idempotency
- Tests and CI from week 1, not bolted on at the end
- One real AWS deployment (ECR + ECS), torn down same day

**Resume outcome:** numbers, not features. See §9.

## 2. Architecture

```
React SPA (static host)
      │  REST/JSON
FastAPI API ─────────── Redis (embed cache + RQ broker)
      │                     │
      │                RQ worker (ingest, embed, retrain)
      │                     │
Postgres + pgvector ◄───────┘
```

Two processes: **API** and **worker**. Postgres and Redis are managed services in prod.

### Request path (`GET /search?q=...`)

1. Embed query (check Redis cache first, keyed on a hash of normalized query + model version)
2. pgvector HNSW ANN → top 100 candidates
3. Cross-encoder scores all 100 (batched, ONNX)
4. Return top 10 with scores; log the search with latency

**Latency budget:** p95 < 500 ms. Step 3 is the expensive one. Making it fast is the interesting engineering.

## 3. Data model

```
papers
  id              serial pk
  arxiv_id        text unique not null      -- idempotency key
  title           text not null
  abstract        text not null
  authors         text[]
  categories      text[]
  published_at    timestamptz
  embedding       vector(384)
  embed_model     text                      -- which model produced it
  created_at      timestamptz default now()
  -- HNSW index on embedding (cosine)

searches
  id, query text, latency_ms int, model_version_id fk, created_at

feedback
  id, search_id fk, paper_id fk, label boolean, created_at
  -- unique (search_id, paper_id): re-clicking updates, doesn't duplicate

model_versions
  id, name text, path text, is_active boolean,
  trained_at timestamptz, metrics jsonb
  -- exactly one active row (partial unique index)
```

`model_versions` is what makes this a system rather than a script. The API loads the active version on boot. Retraining writes a new row; activating it is a separate, deliberate step.

## 4. API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness, DB and Redis reachable |
| GET | `/search?q=&rerank=true` | search; `rerank=false` for comparison |
| GET | `/papers/{id}` | paper detail |
| POST | `/feedback` | `{search_id, paper_id, label}` |
| GET | `/models` | list model versions |
| POST | `/models/{id}/activate` | switch active reranker |

All request/response bodies are Pydantic schemas. Errors return a consistent `{detail: ...}` shape.

## 5. Jobs (RQ)

- **ingest(category, since):** pull from arXiv API, upsert on `arxiv_id`. Rerunning must not create duplicates.
- **embed_missing():** embed papers where `embedding IS NULL` or `embed_model` is stale. Batch size tunable.
- **retrain_reranker():** export feedback as (query, abstract, label) pairs, fine-tune, evaluate against a held-out slice, export ONNX, register a new `model_versions` row. **Runs locally only.**

Every job must be safe to rerun. Retries with backoff for network failures.

## 6. Stack by layer

| Layer | Choice | Why |
|---|---|---|
| Frontend | TS, React, Vite, TanStack Query, Tailwind | explicit client/server boundary; TanStack handles cache and loading states |
| API | FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic | typed, async, migrations are first-class |
| Vector search | pgvector HNSW | one database instead of two; learn indexes properly |
| Cache / queue | Redis + RQ | RQ is enough; Celery is config overhead |
| Embeddings | all-MiniLM-L6-v2 | small, CPU-friendly, 384-dim |
| Rerank | ms-marco-MiniLM-L-6-v2 | small cross-encoder, fine-tunable |
| Serving | ONNX Runtime | keeps PyTorch out of the prod image; fits 512 MB |
| Tests / CI | pytest, Vitest, GitHub Actions | CI on every push from week 1 |

## 7. Deployment

**Local:** docker-compose with api, worker, postgres (pgvector image), redis.

**Prod (free tier):**
- **Postgres:** Neon or Supabase (both support pgvector)
- **Redis:** Upstash
- **API:** a free container host (Render, Koyeb, or Fly.io). **Verify current free-tier terms in week 0; these change often.** Expect cold starts on some.
- **Frontend:** Cloudflare Pages or Vercel
- **Ingest in prod:** scheduled GitHub Actions workflow calling the same ingest function, instead of paying for an always-on worker. Retraining stays local.

**AWS exercise (week 7):** push the existing image to ECR, run it on ECS Fargate pointed at the Neon DB. Set a **$5 billing alarm before creating anything**. Tear down the service and any load balancer the same day.

**Secrets:** env vars on each host; `.env.example` in repo; nothing committed.

## 8. Timeline (8 weeks, ~6 hrs/week)

| Wk | Deliverable | Done when |
|---|---|---|
| 0 | Repo, Docker, FastAPI `/health`, CI running tests, **deployed** | public URL returns 200 |
| 1 | Schema + Alembic, ingest job, 5k papers loaded | rerunning ingest adds 0 rows |
| 2 | Embed job, HNSW index, `/search` (embedding-only) | results make sense; latency logged |
| 3 | React UI: search box, results, loading/error states | usable in browser against prod API |
| 4 | Off-the-shelf cross-encoder rerank, ONNX in serving | p50/p95 recorded before vs. after rerank |
| 5 | Feedback UI + table, `rerank=false` comparison | 100+ labels collected by using it |
| 6 | Local fine-tune job, model versioning, activate endpoint | new version beats baseline on held-out labels, or you know why not |
| 7 | Latency work (batching, caching, quantization), AWS exercise | p95 target met or documented; AWS torn down |
| 8 | README, architecture diagram, cleanup, final deploy | a stranger can run it from the README |

**Week 0 is non-negotiable.** Deploy before the app is complicated.

## 9. Measure

Record these in `DECISIONS.md` as you get them. They become resume bullets.

- `/search` latency p50 / p95: embedding-only vs. reranked
- Rerank latency: PyTorch vs. ONNX, batched vs. unbatched, fp32 vs. int8
- Recall@10 / MRR: embedding-only vs. reranked vs. fine-tuned (on your labeled set)
- Prod image size and memory at idle
- Embedding cache hit rate

## 10. Testing

- Unit: query normalization, cache keys, ranking merge logic
- Integration: API against a real Postgres (test DB in CI via service container)
- Job idempotency: run ingest twice, assert row count unchanged
- Frontend: component tests for search states (loading, empty, error, results)
- CI: lint + tests on every push; deploy only from `main`

## 11. Scope cuts, in order

If behind schedule, drop: (1) fine-tuning (keep off-the-shelf reranker), (2) feedback UI, (3) quantization work.

**Never cut tests or deployment.** Those are what the project exists to teach.

## 12. Non-goals

No auth, no multi-user, no pagination, no Kubernetes, no Spark, no Next.js, no services beyond API + worker.
