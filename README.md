# AI Sales & Order Agent for Social Commerce

This is the **boilerplate scaffold** for the project described in
`PROJECT_PLAN.md`. It is structurally complete and runs (backend health
check, frontend shell) but the core business logic is left as clearly
marked `TODO` stubs, to be implemented phase-by-phase — see
`IMPLEMENTATION_PLAN.md` for the exact phase breakdown, files, and
context each phase needs.

## What's already done

- Full folder structure matching `PROJECT_PLAN.md` section 2.
- `backend/app/config.py` — all env vars declared, reads `.env`.
- `backend/app/db/models.py` — complete SQLAlchemy models for every table
  in the plan's schema (section 5).
- `backend/app/db/session.py` + Alembic scaffolding (`alembic.ini`,
  `env.py`, `script.py.mako`) — ready for `alembic revision --autogenerate`.
- `backend/app/llm/base.py`, `backend/app/tools/registry.py` — complete
  interfaces/schemas taken directly from the plan.
- `backend/app/main.py` — runnable FastAPI app with a `/health` endpoint.
- Frontend: Vite + React + TypeScript + React Router shell, with a nav
  layout and four empty page components, that runs with `npm run dev`.
- `docker-compose.yml` — local Postgres with `pgvector` pre-installed.

## What's left (see IMPLEMENTATION_PLAN.md)

Every file with a `>>> PHASE N TARGET <<<` docstring header needs real
logic. The implementation plan tells you, phase by phase, which files to
hand to an AI assistant (or write yourself) and which files that
assistant needs for context only.

## Local setup

```bash
# 1. Start Postgres (skip if using a hosted DB)
docker compose up -d postgres

# 2. Backend
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then fill in real values
alembic upgrade head         # once Phase 1's models are migrated (see plan)
uvicorn app.main:app --reload

# 3. Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Backend runs at `http://localhost:8000` (health check: `/health`).
Frontend runs at `http://localhost:5173` and proxies `/api` and `/ws` to
the backend (see `frontend/vite.config.ts`).

## Working through the phases

1. Open `IMPLEMENTATION_PLAN.md`.
2. For each phase, give the AI you're using: (a) the phase's description
   from the plan, (b) the exact files listed under "Files to modify" —
   these already exist in this scaffold with TODO docstrings, so ask the
   AI to fill them in, not create new files — and (c) the exact files
   listed under "Context files" (read-only, for reference).
3. Apply the changes back into this project folder, test, move to the
   next phase.
4. Phases are ordered by dependency — do them in order the first time
   through.
