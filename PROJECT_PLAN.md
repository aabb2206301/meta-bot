# AI Sales & Order Agent for Social Commerce — Project Plan

This is the master architecture document. It covers the LLM provider factory
(Groq default, Google as alternate), the tool-calling design so the LLM never
touches the database directly, the full DB schema, folder structure, and a
list of production-grade details that are easy to miss in a fast build.

Everything here is designed around one rule: **you should only ever need to
edit `.env`.** No code changes to switch LLM provider, no code changes to add
a new tool's config, no code changes to point at a different database.

---

## 1. High-Level Architecture

```
 Customer (WhatsApp / Instagram / Facebook)
            │
            ▼
   Channel Webhooks (channels/whatsapp.py, instagram.py, facebook.py)
            │  normalize into one internal message format
            ▼
   Bot Orchestrator (bot/orchestrator.py)
            │  loads conversation history from DB
            │  calls LLM Provider (via factory) with history + tool schemas
            ▼
   LLM Provider (Groq or Google — swappable via env)
            │  returns either a text reply OR one/more tool calls
            ▼
   Tool Executor (tools/*.py)
            │  runs the actual DB read/write, returns result to LLM
            ▼
   Orchestrator sends final reply back through the originating channel
            │
            ▼
   PostgreSQL (all state: customers, conversations, messages, leads,
               orders, products, faqs, KPI rollups)
            ▲
            │
   React Dashboard (reads via REST + WebSocket for live updates)
```

The dashboard and the bot are two separate consumers of the same database —
neither depends on the other being "up" for the core function to work.

---

## 2. Folder Structure

```
project-root/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint
│   │   ├── config.py                # Settings — reads ALL env vars, has defaults
│   │   ├── db/
│   │   │   ├── models.py            # SQLAlchemy models
│   │   │   ├── session.py           # engine/session setup from DATABASE_URL
│   │   │   └── migrations/          # Alembic migration scripts
│   │   ├── llm/
│   │   │   ├── base.py              # LLMProvider abstract interface
│   │   │   ├── groq_provider.py     # Groq implementation
│   │   │   ├── google_provider.py   # Gemini implementation
│   │   │   ├── factory.py           # get_llm_provider() — reads LLM_PROVIDER
│   │   │   └── resilient.py         # wraps provider with retry + fallback
│   │   ├── embeddings/
│   │   │   ├── base.py
│   │   │   ├── google_embeddings.py
│   │   │   └── factory.py           # get_embedding_provider()
│   │   ├── tools/
│   │   │   ├── registry.py          # tool JSON schemas, one list, shared by both LLMs
│   │   │   ├── product_tools.py     # search_products, check_stock
│   │   │   ├── faq_tools.py         # search_faqs
│   │   │   ├── lead_tools.py        # upsert_lead
│   │   │   ├── order_tools.py       # create_order, update_order_status
│   │   │   └── handover_tools.py    # request_human_handover
│   │   ├── channels/
│   │   │   ├── whatsapp.py          # webhook receive + send()
│   │   │   ├── instagram.py
│   │   │   └── facebook.py
│   │   ├── bot/
│   │   │   ├── orchestrator.py      # the conversation loop
│   │   │   └── prompts.py           # system prompt templates
│   │   ├── api/
│   │   │   ├── dashboard_routes.py  # KPIs, conversations, orders, products
│   │   │   └── websocket.py         # live conversation push to dashboard
│   │   └── seed/
│   │       └── seed_data.py         # Faker-based historical data generator
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/                   # Dashboard, Conversations, Orders, Products
│   │   ├── components/
│   │   └── api/                     # fetch wrappers to backend
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml               # optional local Postgres, if not using hosted
├── README.md
└── PROJECT_PLAN.md
```

---

## 3. LLM Provider Factory (Groq default, Google alternate)

### Interface

```python
# backend/app/llm/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall]
    input_tokens: int
    output_tokens: int

class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        """messages: OpenAI-style [{role, content}, ...].
        tools: OpenAI-style function-calling schema (see tools/registry.py).
        Each provider adapter is responsible for translating both into its
        own wire format internally — callers never need to know the difference."""
```

### Groq implementation (default)

```python
# backend/app/llm/groq_provider.py
from groq import AsyncGroq
from .base import LLMProvider, LLMResponse, ToolCall

class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.client = AsyncGroq(api_key=api_key)
        self.model = model

    async def chat(self, messages, tools):
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        choice = resp.choices[0].message
        tool_calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=json.loads(tc.function.arguments))
            for tc in (choice.tool_calls or [])
        ]
        return LLMResponse(
            text=choice.content,
            tool_calls=tool_calls,
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
        )
```

Groq's API is OpenAI-compatible, so the tool schema in `tools/registry.py` is
written once, in OpenAI's format, and passed straight through here.

### Google implementation (alternate)

```python
# backend/app/llm/google_provider.py
from google import genai
from google.genai import types
from .base import LLMProvider, LLMResponse, ToolCall

class GoogleProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def chat(self, messages, tools):
        gemini_tools = _convert_openai_tools_to_gemini(tools)   # adapter, one function
        contents = _convert_messages_to_gemini(messages)        # adapter, one function
        resp = await self.client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(tools=gemini_tools),
        )
        # ... extract text / function_call parts into LLMResponse, same shape as Groq
        return LLMResponse(...)
```

The two small `_convert_*` adapter functions are the *only* place that knows
Gemini's wire format is different from OpenAI's — everything else in the
codebase (orchestrator, tools) only ever sees the shared `LLMResponse` shape.

### Factory

```python
# backend/app/llm/factory.py
from .groq_provider import GroqProvider
from .google_provider import GoogleProvider
from ..config import settings

_PROVIDERS = {"groq": GroqProvider, "google": GoogleProvider}

def get_llm_provider() -> LLMProvider:
    name = settings.llm_provider.lower()
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER '{name}'. Use 'groq' or 'google'.")
    if name == "groq":
        if not settings.groq_api_key:
            raise ValueError("LLM_PROVIDER=groq but GROQ_API_KEY is not set.")
        return GroqProvider(settings.groq_api_key, settings.groq_model)
    if not settings.google_api_key:
        raise ValueError("LLM_PROVIDER=google but GOOGLE_API_KEY is not set.")
    return GoogleProvider(settings.google_api_key, settings.google_model)
```

Adding a third provider later (OpenAI, Anthropic, whatever) means: one new
file implementing `LLMProvider`, one new line in `_PROVIDERS`. Nothing else
in the app changes — that's the point of the factory pattern here.

### Automatic fallback (resilience, not just switching)

```python
# backend/app/llm/resilient.py
class ResilientLLM(LLMProvider):
    """Wraps the primary provider; on failure (rate limit, timeout, 5xx),
    retries once, then falls back to the secondary provider if configured
    and LLM_FALLBACK_ENABLED=true. This is what makes 'default + alternate'
    actually useful at runtime, not just a config toggle you flip by hand."""
```

This means if Groq rate-limits you mid-demo, the bot can silently continue
on Google instead of the conversation just dying. Only kicks in if both
keys are present and `LLM_FALLBACK_ENABLED=true`.

### Embeddings (needed for product/FAQ search — separate from chat)

Groq does not currently offer an embeddings endpoint, so embeddings default
to Google regardless of which provider you pick for chat. Same factory
pattern (`embeddings/factory.py`), controlled by `EMBEDDING_PROVIDER` /
`EMBEDDING_MODEL` env vars, defaulting to Google's `text-embedding-004`.
If Google isn't configured either, fall back to plain keyword search
(`ILIKE` / Postgres full-text search) — slower to build well, but zero
external dependency, and worth having as a floor.

---

## 4. Tool-Calling Design (LLM never touches the DB directly)

The LLM only ever sees a fixed list of named tools with JSON-schema
parameters. It returns a tool name + arguments; **your backend code**
executes the actual database operation and returns the result as a new
message in the conversation, which the LLM then uses to write its reply.

```python
# backend/app/tools/registry.py  (OpenAI-format schema — shared by both providers)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search the catalog by name, category, or description. Use whenever a customer asks about a product, price, or availability.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_faqs",
            "description": "Search business FAQs — shipping, returns, policies.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "upsert_lead",
            "description": "Create or update the lead record for this conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["new", "qualified", "hot", "lost"]},
                    "product_interest_id": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Create an order once product, quantity, address, and payment method (COD only) are all confirmed with the customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "address": {"type": "string"},
                    "payment_method": {"type": "string", "enum": ["cod"]},
                },
                "required": ["product_id", "quantity", "address", "payment_method"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_human_handover",
            "description": "Flag the conversation for a staff member when the bot cannot confidently continue.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"],
            },
        },
    },
]
```

```python
# backend/app/tools/order_tools.py
async def create_order(db, *, conversation_id: str, args: dict) -> dict:
    """conversation_id comes from the webhook context, injected by the
    orchestrator — NEVER from the LLM's arguments. Only product_id,
    quantity, address, payment_method are LLM-supplied. This boundary
    matters: if you let the model supply conversation_id or customer_id,
    a manipulated conversation could write orders against someone else's
    account. Content parameters from the LLM, identity parameters from
    your own trusted context — always."""
    conversation = await get_conversation(db, conversation_id)
    order = await db_create_order(
        db,
        customer_id=conversation.customer_id,
        product_id=args["product_id"],
        quantity=args["quantity"],
        address=args["address"],
        payment_method=args["payment_method"],
    )
    return {"order_id": str(order.id), "status": order.status}
```

The orchestrator loop, in plain terms:

1. Load last N messages for this conversation from `messages` table.
2. Call `llm.chat(history + new_message, tools=TOOLS)`.
3. If response has `tool_calls`: execute each via the matching function in
   `tools/`, append the tool result to the message list, call the LLM again
   (it now has the result and can either call another tool or write a reply).
4. Once the LLM returns plain text, send it to the customer via the
   originating channel's `send()` function, and store both the tool
   calls/results and the final text in the `messages` table.

---

## 5. Database Schema

PostgreSQL, with `pgvector` for product/FAQ semantic search.

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE channel_type AS ENUM ('whatsapp', 'instagram', 'facebook');
CREATE TYPE conversation_status AS ENUM ('open', 'handed_over', 'closed');
CREATE TYPE sender_type AS ENUM ('customer', 'bot', 'staff');
CREATE TYPE lead_status AS ENUM ('new', 'qualified', 'hot', 'lost', 'converted');
CREATE TYPE order_status AS ENUM ('pending', 'confirmed', 'fulfilled', 'cancelled');
CREATE TYPE staff_role AS ENUM ('owner', 'agent');

-- Future-proofing: even for a single-seller demo, scope everything under
-- a "business" row now. Retrofitting multi-tenancy later means touching
-- every table; adding it now costs one extra foreign key per table.
CREATE TABLE businesses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE staff_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role staff_role NOT NULL DEFAULT 'agent',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT,
    phone TEXT,
    instagram_handle TEXT,
    facebook_psid TEXT,
    email TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, phone),
    UNIQUE (business_id, instagram_handle),
    UNIQUE (business_id, facebook_psid)
);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    price NUMERIC(10,2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    stock_qty INT NOT NULL DEFAULT 0,
    image_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    embedding vector(768),   -- match your embedding model's output dimension
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE faqs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    category TEXT,
    embedding vector(768),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    channel channel_type NOT NULL,
    status conversation_status NOT NULL DEFAULT 'open',
    assigned_staff_id UUID REFERENCES staff_users(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_message_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_conversations_customer ON conversations(customer_id);
CREATE INDEX idx_conversations_status ON conversations(status);

-- This is the table that makes historical context possible: every message,
-- every tool call, every tool result, in order, per conversation. The
-- orchestrator reads the last N rows here to reconstruct context for the LLM.
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    sender sender_type NOT NULL,
    content TEXT,
    tool_calls JSONB,
    tool_results JSONB,
    external_message_id TEXT,   -- Meta's message ID, for de-duplication
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (conversation_id, external_message_id)
);
CREATE INDEX idx_messages_conversation_time ON messages(conversation_id, created_at);

CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    status lead_status NOT NULL DEFAULT 'new',
    score INT DEFAULT 0,
    product_interest_id UUID REFERENCES products(id),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_leads_status ON leads(status);

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID REFERENCES leads(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    status order_status NOT NULL DEFAULT 'pending',
    payment_method TEXT DEFAULT 'cod',
    address TEXT,
    total_amount NUMERIC(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_orders_status ON orders(status);

CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES orders(id),
    product_id UUID NOT NULL REFERENCES products(id),
    quantity INT NOT NULL,
    unit_price NUMERIC(10,2) NOT NULL
);

-- Daily rollups so dashboard charts don't aggregate 1,000+ raw rows on
-- every page load. Populate via a scheduled job (or recompute on seed).
CREATE TABLE kpi_daily_snapshot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    date DATE NOT NULL,
    channel channel_type,
    enquiries_count INT DEFAULT 0,
    ai_resolved_count INT DEFAULT 0,
    avg_response_seconds NUMERIC(8,2),
    orders_count INT DEFAULT 0,
    revenue NUMERIC(12,2) DEFAULT 0,
    UNIQUE (business_id, date, channel)
);

-- Cost/latency visibility per LLM call — doubles as a KPI ("cost per
-- conversation") and as debugging data when a provider misbehaves.
CREATE TABLE llm_call_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID REFERENCES conversations(id),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INT,
    output_tokens INT,
    latency_ms INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Use **Alembic** to manage this as migrations rather than running the raw
SQL by hand — `DATABASE_URL` from `.env` drives both the app and Alembic,
so there's one source of truth for where the database lives.

---

## 6. Things worth knowing that hadn't come up yet

- **Meta retries webhook deliveries.** If your server doesn't ack fast
  enough, or errors, Meta re-sends the same event. The `UNIQUE
  (conversation_id, external_message_id)` constraint above is what stops
  a retried delivery from making the bot reply twice to the same message.
- **Meta expects a fast webhook ack, not a fast reply.** Respond `200 OK`
  to the webhook immediately, then run the actual LLM call + reply
  send as a background task. If you make Meta wait on your LLM call inside
  the webhook handler itself, slow responses can cause Meta to consider
  the webhook unhealthy.
- **Verify webhook signatures.** Meta signs each webhook payload with
  `X-Hub-Signature-256`, computed from your `META_APP_SECRET`. Check it
  before processing — otherwise anyone who finds your webhook URL can
  inject fake "customer messages."
- **Cap conversation history sent to the LLM.** Sending the entire message
  table for a long-running conversation gets expensive and slow fast —
  window to the last ~15-20 messages, or summarize older context into a
  single system-message blurb once a conversation gets long.
- **Rate-limit the webhook endpoint and the LLM calls per conversation**,
  so a message flood (or a bug that loops) can't run up a bill or lock the
  bot in a retry storm.
- **`.env` must never be committed** — add it to `.gitignore` on day one,
  and keep `.env.example` (no real values) as the thing that *does* go
  into version control.
