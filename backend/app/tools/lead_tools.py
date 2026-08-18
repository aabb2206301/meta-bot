"""
upsert_lead — create or update the lead row for the current conversation.

>>> PHASE 3 TARGET — implement per PROJECT_PLAN.md sections 3-4 <<<

TODO:
- async def upsert_lead(db, *, conversation_id: str, customer_id: str, args: dict) -> dict:
    - conversation_id and customer_id are injected by the orchestrator
      from trusted webhook context — NEVER from LLM arguments (same
      trust boundary as order_tools.create_order).
    - args contains: status (required), product_interest_id (optional),
      notes (optional) — all LLM-supplied content, which is fine.
    - Look up an existing Lead by conversation_id; if found, update
      status/product_interest_id/notes and updated_at; if not, INSERT.
    - Return {"lead_id", "status"}.
"""


async def upsert_lead(db, *, conversation_id: str, customer_id: str, args: dict) -> dict:
    raise NotImplementedError("Phase 3: implement upsert_lead")
