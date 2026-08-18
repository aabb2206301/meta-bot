# Implementation Plan — AI Sales & Order Agent

This plan picks up where the boilerplate (`project-root.zip`) leaves off.
Every file below already exists in the scaffold with a `>>> PHASE N
TARGET <<<` docstring explaining what's needed — hand each phase to an AI
as **"implement the TODOs in these files"**, not "create these files".

**Rule respected throughout:** every file is modified in exactly one
phase. If a later phase needs to touch a file from an earlier phase, it's
called out explicitly as an exception (only happens once, in Phase 6).

**How to hand off a phase to an AI (any AI — Claude, ChatGPT, etc.):**
1. Paste the phase's "Goal" and "Changes required" text below.
2. Attach/paste the **files to modify** (the current stub content).
3. Attach/paste the **context files** (read-only reference — don't ask
   the AI to change these).
4. Attach `PROJECT_PLAN.md` too — it's referenced by section number
   throughout and every stub docstring points back to it.
5. Ask it to return the complete, updated content of each file to modify.
6. Paste the results back into your local project folder and test before
   moving to the next phase.

Do the phases in order the first time through — each one depends on the
previous.

---

## Phase 1 — LLM Provider Layer

**Goal:** Make `get_llm_provider()` return a working Groq or Google
client that satisfies the shared `LLMProvider` interface, with automatic
fallback between them.

**Files to modify:**
- `backend/app/llm/groq_provider.py` — implement `GroqProvider.__init__`
  and `.chat()`.
- `backend/app/llm/google_provider.py` — implement `GoogleProvider`,
  including the two `_convert_*` adapter functions.
- `backend/app/llm/factory.py` — implement `get_llm_provider()`.
- `backend/app/llm/resilient.py` — implement `ResilientLLM`.

**Context files (read-only):**
```
[backend/app/llm/base.py, backend/app/config.py, backend/.env.example, backend/requirements.txt, PROJECT_PLAN.md]
```

**Notes for the AI:** `PROJECT_PLAN.md` section 3 has near-complete
reference code for `GroqProvider` and the `factory()` function — verify
it against whatever `groq` and `google-genai` SDK versions are pinned in
`requirements.txt`, since tool-call response shapes shift between SDK
versions. Decide and document whether `ResilientLLM` wrapping happens
inside `factory.py` or is left to the caller (Phase 4) — pick one.

---

## Phase 2 — Embeddings Layer

**Goal:** Make `get_embedding_provider()` return a working Google
embeddings client, or `None` when unconfigured (so callers fall back to
keyword search instead of crashing).

**Files to modify:**
- `backend/app/embeddings/google_embeddings.py`
- `backend/app/embeddings/factory.py`

**Context files (read-only):**
```
[backend/app/embeddings/base.py, backend/app/config.py, backend/app/db/models.py, PROJECT_PLAN.md]
```

**Notes for the AI:** The embedding vector's output dimension must equal
`settings.embedding_dimensions` (768 by default), which must match the
`Vector(768)` column width already defined in `db/models.py` for
`Product.embedding` and `Faq.embedding`. If you change the model/
dimensions, flag that both places need to change together.

---

## Phase 3 — Tool Implementations

**Goal:** Implement the six tool functions the bot can call. This is the
trust boundary: identity fields (`business_id`, `conversation_id`,
`customer_id`) come from the orchestrator's trusted context, never from
LLM arguments — the plan is explicit about this and it's the single most
important thing to get right in this phase.

**Files to modify:**
- `backend/app/tools/product_tools.py` — `search_products`, `check_stock`
- `backend/app/tools/faq_tools.py` — `search_faqs`
- `backend/app/tools/lead_tools.py` — `upsert_lead`
- `backend/app/tools/order_tools.py` — `create_order`, `update_order_status`
- `backend/app/tools/handover_tools.py` — `request_human_handover`

**Context files (read-only):**
```
[backend/app/tools/registry.py, backend/app/db/models.py, backend/app/db/session.py, backend/app/embeddings/factory.py, backend/app/embeddings/base.py, PROJECT_PLAN.md]
```

**Notes for the AI:** `PROJECT_PLAN.md` section 4 gives a near-complete
reference implementation for `create_order` — follow its trust-boundary
comment closely and apply the same pattern to `update_order_status`
(verify `order.customer_id` matches the trusted caller before allowing
any change). `create_order` must decrement `Product.stock_qty` and
create the matching `OrderItem` row in the same transaction.

---

## Phase 4 — Bot Orchestrator

**Goal:** Implement the actual conversation loop: load history, call the
LLM, dispatch tool calls, loop until a plain-text reply, persist
everything.

**Files to modify:**
- `backend/app/bot/prompts.py` — `build_system_prompt`
- `backend/app/bot/orchestrator.py` — `handle_incoming_message`

**Context files (read-only):**
```
[backend/app/llm/factory.py, backend/app/llm/base.py, backend/app/tools/registry.py, backend/app/tools/product_tools.py, backend/app/tools/faq_tools.py, backend/app/tools/lead_tools.py, backend/app/tools/order_tools.py, backend/app/tools/handover_tools.py, backend/app/db/models.py, backend/app/db/session.py, backend/app/config.py, PROJECT_PLAN.md]
```

**Notes for the AI:** Use `TOOL_DISPATCH_MAP` from `tools/registry.py` to
resolve tool name → function rather than an if/elif chain. Cap the
tool-call loop (e.g. 5 rounds) to prevent runaway cost. Every LLM call
must be logged to `llm_call_log` (provider, model, tokens, latency_ms —
the table already exists in `db/models.py`). This file returns plain
text only — no channel-specific formatting (that's Phase 5's job).

---

## Phase 5 — Channel Webhooks

**Goal:** Receive and verify WhatsApp/Instagram/Facebook webhooks, ack
fast, process in the background, and send replies back out.

**Files to modify:**
- `backend/app/channels/whatsapp.py`
- `backend/app/channels/instagram.py`
- `backend/app/channels/facebook.py`

**Context files (read-only):**
```
[backend/app/bot/orchestrator.py, backend/app/bot/prompts.py, backend/app/config.py, backend/app/db/models.py, backend/app/db/session.py, PROJECT_PLAN.md]
```

**Notes for the AI:** `PROJECT_PLAN.md` section 6 covers three things
that are easy to get wrong here and must all be respected: (1) verify
`X-Hub-Signature-256` against `META_APP_SECRET` before processing
anything, (2) return `200 OK` immediately and do the actual LLM call as
a background task — don't make Meta wait on the LLM, (3) rely on the
existing `UNIQUE(conversation_id, external_message_id)` constraint on
`messages` to silently no-op retried webhook deliveries. Consider
factoring the signature-check logic into one shared helper used by all
three files instead of copy-pasting it three times.

---

## Phase 6 — Main App Wiring + Dashboard API + WebSocket

**Goal:** Wire up the FastAPI app's routers and build the REST + WS
surface the React dashboard consumes.

**Files to modify:**
- `backend/app/main.py` — uncomment and register all routers.
- `backend/app/api/dashboard_routes.py` — auth + KPI/conversation/order/
  product endpoints.
- `backend/app/api/websocket.py` — live push connection manager.

**One-time exception to the "one phase per file" rule:** `websocket.py`
needs `bot/orchestrator.py` (Phase 4) to call its broadcast function
after persisting a message. This phase is allowed to add **one single
function call** into `orchestrator.py` for that purpose — nothing else
in that file should change. Flag this to the AI explicitly so it doesn't
rewrite unrelated parts of `orchestrator.py`.

**Context files (read-only):**
```
[backend/app/channels/whatsapp.py, backend/app/channels/instagram.py, backend/app/channels/facebook.py, backend/app/bot/orchestrator.py, backend/app/db/models.py, backend/app/db/session.py, backend/app/config.py, PROJECT_PLAN.md]
```

**Notes for the AI:** Every route except `/api/auth/login` must require a
valid JWT and scope every query by the `business_id` encoded in it — same
trust-boundary principle as Phase 3, applied to staff instead of the bot.
A single in-process connection manager (dict keyed by `business_id`) is
enough for a single-instance deployment; note in a comment that a
multi-instance deployment would need Postgres LISTEN/NOTIFY or Redis, but
don't build that now.

---

## Phase 7 — Seed Data Script

**Goal:** Generate realistic historical data so the dashboard isn't empty
on first run.

**Files to modify:**
- `backend/app/seed/seed_data.py`

**Context files (read-only):**
```
[backend/app/db/models.py, backend/app/db/session.py, backend/app/config.py, backend/requirements.txt, PROJECT_PLAN.md]
```

**Notes for the AI:** Must produce one `Business` row (print its id — the
user pastes it into `.env` as `BUSINESS_ID`), a spread of customers/
conversations/messages/leads/orders/products/faqs over the last ~60 days,
and pre-aggregated `kpi_daily_snapshot` rows (don't make the dashboard
aggregate raw rows on every page load). Leave `embedding` columns NULL
during seeding to avoid burning API quota — call this out as a known
limitation in a comment.

---

## Phase 8 — Frontend API Client + Layout + Routing polish

**Goal:** Add typed endpoint functions to the API client and finish
auth/login wiring.

**Files to modify:**
- `frontend/src/api/client.ts` — add typed functions per endpoint
  (`getKpiSummary`, `listConversations`, `getConversationMessages`,
  `listOrders`, `listProducts`, etc.) plus matching TypeScript interfaces.
- `frontend/src/App.tsx` — add a login redirect when no JWT is present.
- `frontend/src/components/Layout.tsx` — styling/branding polish only
  (structure is already complete — don't restructure it).

**Context files (read-only):**
```
[backend/app/api/dashboard_routes.py, backend/app/api/websocket.py, PROJECT_PLAN.md]
```

**Notes for the AI:** The TypeScript interfaces in `client.ts` should
mirror the backend's Pydantic response models field-for-field — mismatch
here is the most common source of silent frontend bugs.

---

## Phase 9 — Frontend: Dashboard & Conversations Pages

**Goal:** Build the two most data-dense pages.

**Files to modify:**
- `frontend/src/pages/Dashboard.tsx` — KPI stat cards + trend charts
  (recharts, already a dependency).
- `frontend/src/pages/Conversations.tsx` — conversation list + live
  message thread over the dashboard websocket.

**Context files (read-only):**
```
[frontend/src/api/client.ts, frontend/src/components/Layout.tsx, backend/app/api/dashboard_routes.py, backend/app/api/websocket.py, PROJECT_PLAN.md]
```

**Notes for the AI:** Render `tool_calls`/`tool_results` in the message
thread as a muted, collapsed "system" line — not as a chat bubble, since
they aren't conversation content. Handed-over conversations should be
visually distinct in the list (that's the "needs a human" queue).

---

## Phase 10 — Frontend: Orders & Products Pages

**Goal:** Build the two CRUD-style pages.

**Files to modify:**
- `frontend/src/pages/Orders.tsx`
- `frontend/src/pages/Products.tsx`

**Context files (read-only):**
```
[frontend/src/api/client.ts, frontend/src/components/Layout.tsx, backend/app/api/dashboard_routes.py, PROJECT_PLAN.md]
```

**Notes for the AI:** `Orders.tsx`'s status control writes through
`PATCH /api/orders/{id}` — this is the human/staff path and is separate
from the bot's `update_order_status` tool, but should end up writing the
same columns. `Products.tsx` should flag low stock (`stock_qty < 5`) —
this is the same raw column the bot's `check_stock` tool reads, so
keep both consistent with the single source of truth.

---

## Phase 11 — Initial Migration + Deployment Finalization

**Goal:** Generate the first real Alembic migration from the models, and
finalize the deployment artifacts.

**Files to modify:**
- `backend/app/db/migrations/versions/` — generate
  `0001_initial.py` (via `alembic revision --autogenerate -m "initial schema"`,
  run against a real Postgres instance with the `vector` extension
  available — don't hand-write this one).
- `docker-compose.yml` — add `backend` and `frontend` services alongside
  the existing `postgres` service, if you want a single `docker compose
  up` to run everything (optional — the README's manual steps work fine
  without this).
- `README.md` — fill in any deployment-specific notes that came up while
  running Phases 1–10 (e.g. actual model names that worked, gotchas).

**Context files (read-only):**
```
[backend/app/db/models.py, backend/app/config.py, backend/.env.example, docker-compose.yml]
```

**Notes for the AI:** Run `CREATE EXTENSION IF NOT EXISTS vector;` and
`CREATE EXTENSION IF NOT EXISTS "uuid-ossp";` against the target database
before running the migration — `pgvector/pgvector:pg16`, the image
already used in `docker-compose.yml`, has the extension available but
doesn't enable it automatically. If you add `backend`/`frontend` services
to `docker-compose.yml`, you'll also need a `backend/Dockerfile` and
`frontend/Dockerfile` — neither exists yet in the scaffold, so write them
as part of this phase if you take the docker-compose route.

---

## Quick reference — phase → files table

| Phase | Modifies | Depends on |
|---|---|---|
| 1 | LLM providers, factory, resilient | — |
| 2 | Embedding providers, factory | — |
| 3 | All `tools/*.py` | Phase 2 |
| 4 | `bot/orchestrator.py`, `bot/prompts.py` | Phases 1, 3 |
| 5 | `channels/*.py` | Phase 4 |
| 6 | `main.py`, `api/*.py` (+ 1-line hook into `orchestrator.py`) | Phase 5 |
| 7 | `seed/seed_data.py` | — (needs models only, can run in parallel with 1–6) |
| 8 | `frontend/src/api/client.ts`, `App.tsx`, `Layout.tsx` polish | Phase 6 |
| 9 | `Dashboard.tsx`, `Conversations.tsx` | Phase 8 |
| 10 | `Orders.tsx`, `Products.tsx` | Phase 8 |
| 11 | Initial migration, deployment files | Phases 1–10 |
