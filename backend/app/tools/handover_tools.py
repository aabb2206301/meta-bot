"""
request_human_handover — flips conversation.status to 'handed_over' and
(eventually) notifies staff via the dashboard's websocket channel.

>>> PHASE 3 TARGET — implement per PROJECT_PLAN.md sections 3-4 <<<

TODO:
- async def request_human_handover(db, *, conversation_id: str, args: dict) -> dict:
    - conversation_id injected by the orchestrator (trusted), args["reason"]
      is LLM-supplied.
    - Update the Conversation row: status = 'handed_over'.
    - Store args["reason"] somewhere retrievable by staff — either as a
      Message row (sender='bot', content=f"[handover] {reason}") or a
      dedicated column if you decide the schema needs one. If you add a
      column, add the matching Alembic migration in the same change.
    - Return {"conversation_id", "status": "handed_over"}.
    - Actually pushing a live notification to the dashboard is Phase 6's
      job (api/websocket.py) — this function only needs to leave the DB
      in a state the websocket layer can react to (e.g. poll or listen
      for status='handed_over').
"""


async def request_human_handover(db, *, conversation_id: str, args: dict) -> dict:
    raise NotImplementedError("Phase 3: implement request_human_handover")
