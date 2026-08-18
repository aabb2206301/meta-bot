# AI Sales & Order Agent for Social Commerce

Multi-channel AI sales agent for social commerce (WhatsApp / Instagram / Facebook Messenger). Built per `PROJECT_PLAN.md`, implemented phase-by-phase per `IMPLEMENTATION_PLAN.md`. All 11 phases are complete.

## What's in the box

- **Backend** (FastAPI + SQLAlchemy 2 + asyncpg + Alembic + pgvector)
  - LLM provider layer: Groq (default) + Google Gemini, with automatic fallback
  - Embedding provider: Google `text-embedding-004` (768-dim), keyword fallback
  - 6 bot tools (search products/FAQs, upsert lead, create/update order, request human handover) with strict trust boundaries
  - Channel webhooks for WhatsApp / Instagram / Facebook with `X-Hub-Signature-256` verification
  - Bot orchestrator that loads history, calls the LLM, dispatches tool calls, persists everything
  - Dashboard REST + WebSocket for the live React UI
  - Seed script that creates a `Business` + 60 days of demo data
- **Frontend** (Vite + React + TypeScript + recharts)
  - Dashboard (KPI cards + line/bar charts)
  - Conversations (filterable list + live message thread + staff reply)
  - Orders (filterable table with status updates)
  - Products (card grid with add/edit modal + low-stock indicators)
- **Deployment**: Postgres with pgvector, Dockerfiles for backend + frontend, full `docker-compose.yml` for `docker compose up -d --build`

## Quick start (Docker, full stack)

```bash
# 1. Fill in real values (LLM keys, JWT secret, etc.)
cp backend/.env.example backend/.env
# then edit backend/.env

# 2. Bring up postgres + backend + frontend
docker compose up -d --build

# 3. (One-time, only on fresh DB volumes) enable extensions
#    If the data volume was empty, db/init.sql already did this. If not:
docker compose exec postgres psql -U postgres -d sales_agent \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker compose exec postgres psql -U postgres -d sales_agent \
  -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'

# 4. Apply migrations (the backend Dockerfile also runs this on boot,
#    but it's idempotent so re-running is safe)
docker compose exec backend alembic upgrade head

# 5. (Optional) seed demo data — prints the BUSINESS_ID; paste it
#    into backend/.env as BUSINESS_ID=... and restart the backend
docker compose exec backend python -m app.seed.seed_data
docker compose restart backend
```

Then open:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs

## Quick start (manual — backend/frontend on host, only Postgres in Docker)

```bash
# 1. Start just the database
docker compose up -d postgres

# 2. Enable extensions
docker compose exec postgres psql -U postgres -d sales_agent \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker compose exec postgres psql -U postgres -d sales_agent \
  -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'

# 3. Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in real values
alembic upgrade head
uvicorn app.main:app --reload

# 4. Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Configuration

All config is via `backend/.env`. Required for first run:
- `DATABASE_URL` (defaults to local Postgres)
- `LLM_PROVIDER` = `groq` (default) or `google`
- The matching API key — `GROQ_API_KEY` or `GOOGLE_API_KEY`
- `JWT_SECRET` (anything long and random; the placeholder is fine for dev)

Optional (needed to actually receive/send on live channels):
- `META_APP_SECRET` + `META_VERIFY_TOKEN`
- `WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID`
- `INSTAGRAM_PAGE_ACCESS_TOKEN` + `INSTAGRAM_PAGE_ID`
- `FACEBOOK_PAGE_ACCESS_TOKEN` + `FACEBOOK_PAGE_ID`

After seeding, the seed script prints a `BUSINESS_ID` — paste that into `.env` too so the bot's runtime context has a tenant.

## Gotchas & known limitations

These came up during the build. All of them are flagged in code comments at the point of impact, but a top-level list helps.

- **`SenderType` is the enum name** — not `MessageSender`. The model in `backend/app/db/models.py` defines it as `SenderType`. If you generated Phase 9's `dashboard_routes.py` and used `MessageSender`, fix the import (and the `MessageSender.STAFF` usage → `SenderType.STAFF`) before running migrations or the import will fail on first request.
- **Embedding staleness on product edit.** `PATCH /api/products/{id}` does not re-embed after changing `description` / `price` / `stock_qty` — the existing vector becomes stale. The endpoint logs a warning when this happens; a follow-up pass should re-embed on save (calls `embeddings/factory.py`).
- **Staff reply does NOT go out to the customer.** `POST /api/conversations/{id}/messages` (added in Phase 9) persists the message and broadcasts to dashboards, but does not call `channels/{channel}.py:send()` to deliver to the customer. Full staff-reply path needs outbound channel dispatch — deferred from Phase 9 scope.
- **Single-instance dashboard only.** `ConnectionManager` in `api/websocket.py` is in-process. Multi-instance deployments need Postgres `LISTEN`/`NOTIFY` or Redis pub/sub. The plan explicitly leaves this as a known scope cut.
- **Embedding dimension is hardcoded to 768** in the model (`Product.embedding`, `Faq.embedding`) and the migration (`Vector(768)`). If you change `EMBEDDING_DIMENSIONS` in `app/config.py`, you also need a new migration to alter the column.
- **No `message_id` on the WS broadcast for staff messages.** The sender's dashboard dedupes on `(sender, content, recent)` to avoid a double-render. For a real fix, include the new message's `id` in the broadcast payload and dedup on id.
- **`kpi_daily_snapshot.date` is VARCHAR**, not a real `DATE` column. The query layer relies on ISO `YYYY-MM-DD` lexical ordering, which works correctly but isn't type-safe.
- **Initial migration was hand-written** in Phase 11, not `alembic revision --autogenerate`. The output should match what autogenerate would produce, but if you want to verify, run `alembic revision --autogenerate -m "verify initial"` against a fresh DB and diff. The revision id is `0001_initial`.
- **Seed data leaves `embedding` columns NULL** to avoid burning LLM quota. Re-embed in a follow-up pass (or accept the keyword-search fallback for seeded products/FAQs).

## Project layout

```
project-root/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint
│   │   ├── config.py                # ALL env vars, single source of truth
│   │   ├── db/
│   │   │   ├── models.py            # SQLAlchemy models
│   │   │   ├── session.py           # async engine
│   │   │   └── migrations/versions/0001_initial.py
│   │   ├── llm/                     # Groq, Google, Resilient, factory
│   │   ├── embeddings/              # Google embeddings + factory
│   │   ├── tools/                   # 6 tool impls + OpenAI-format registry
│   │   ├── channels/                # WhatsApp / Instagram / Facebook webhooks
│   │   ├── bot/                     # orchestrator + system prompts
│   │   ├── api/                     # dashboard REST + WebSocket
│   │   └── seed/                    # seed_data.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/                   # Dashboard, Conversations, Orders, Products
│   │   ├── components/Layout.tsx
│   │   └── api/client.ts
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── db/
│   └── init.sql                     # auto-loaded by postgres image on first start
├── docker-compose.yml
├── PROJECT_PLAN.md                  # architecture / schema / tool design
├── IMPLEMENTATION_PLAN.md           # 11-phase build plan
└── README.md
```

## Phase-by-phase status

All 11 phases of `IMPLEMENTATION_PLAN.md` are done.

| Phase | Scope | Status |
|---|---|---|
| 1 | LLM providers (Groq / Google / Resilient) | done |
| 2 | Embedding provider (Google) | done |
| 3 | 6 tool implementations with trust boundaries | done |
| 4 | Bot orchestrator + prompts | done |
| 5 | Channel webhooks (WhatsApp / IG / FB) | done |
| 6 | Main FastAPI + dashboard REST/WS | done |
| 7 | Seed data script | done |
| 8 | Frontend API client + layout polish | done |
| 9 | Dashboard + Conversations + staff reply | done |
| 10 | Orders + Products pages | done |
| 11 | Initial migration + Docker + this README | done |
