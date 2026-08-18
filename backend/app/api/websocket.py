"""
Live conversation push to the dashboard — so staff see new
customer/bot messages without polling, and get notified the moment
request_human_handover fires.

>>> PHASE 6 TARGET — implement per PROJECT_PLAN.md section 1 <<<

TODO:
- WebSocket endpoint, e.g. `/ws/conversations` (auth: accept a JWT as a
  query param since browsers can't set headers on the initial WS
  handshake — verify it the same way dashboard_routes.py does).
- A simple in-process connection manager (dict of business_id -> set of
  open WebSocket connections) is enough for a single-instance demo
  deployment; note in a comment that a multi-instance deployment would
  need Postgres LISTEN/NOTIFY or Redis pub/sub instead, but don't build
  that now.
- Something needs to CALL this manager's broadcast method whenever a new
  message is written or a conversation is handed over — the natural
  place is bot/orchestrator.py (Phase 4) after it persists a message, or
  the channel webhook handlers (Phase 5) after send(). Since Phase 4 and
  5 are already implemented by the time this phase runs, wiring the
  broadcast call means a small edit back into orchestrator.py — flag
  this explicitly to whoever implements this phase, since it's the one
  place this plan asks you to touch a file outside this phase's list;
  keep the edit to a single broadcast() call, nothing structural.
- Register this router in main.py.
"""
from fastapi import APIRouter

router = APIRouter(tags=["websocket"])
