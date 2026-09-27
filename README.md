# papers

Semantic search over recent arXiv papers. See `DESIGN.md`.

Live API: https://papers-njsd.onrender.com/health (free tier; first request after 15 min idle is slow)

## Local setup

```
cp backend/.env.example backend/.env   # DATABASE_URL is required; the app won't start without it
make up
make migrate
```
