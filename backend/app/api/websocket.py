"""
Live conversation push to the dashboard — so staff see new
customer/bot messages without polling, and get notified the moment
request_human_handover fires.

Implemented per PROJECT_PLAN.md section 1.
"""
import logging

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from .auth import decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """
    In-process registry: business_id -> set of open WebSocket
    connections. Good enough for a single-instance demo deployment.

    A multi-instance deployment would need Postgres LISTEN/NOTIFY or
    Redis pub/sub to fan a broadcast() call out across processes —
    intentionally not built here, per PROJECT_PLAN.md scope.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, business_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(business_id, set()).add(websocket)

    def disconnect(self, business_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(business_id)
        if conns is not None:
            conns.discard(websocket)
            if not conns:
                self._connections.pop(business_id, None)

    async def broadcast(self, business_id: str, payload: dict) -> None:
        conns = self._connections.get(business_id)
        if not conns:
            return
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 - one broken socket must not
                # stop delivery to the other staff members connected.
                dead.append(ws)
        for ws in dead:
            self.disconnect(business_id, ws)


manager = ConnectionManager()


async def broadcast_new_message(*, business_id: str, conversation_id: str, text: str) -> None:
    """
    Called from bot/orchestrator.py after it persists the bot's final
    reply for a turn — this is the one-line hook into orchestrator.py
    that IMPLEMENTATION_PLAN.md's Phase 6 section explicitly allows.

    Scope note: this only covers the final plain-text reply per turn.
    A dedicated, immediate "handover just happened" event and per-round
    tool-call pushes are a known gap — left for a later pass rather than
    expanding the orchestrator.py edit beyond the single call the plan
    calls for.
    """
    await manager.broadcast(
        business_id,
        {
            "type": "message",
            "conversation_id": str(conversation_id),
            "sender": "bot",
            "content": text,
        },
    )


@router.websocket("/ws/conversations")
async def conversations_ws(websocket: WebSocket, token: str | None = None):
    """
    Browsers can't set headers on the initial WS handshake, so the JWT is
    passed as a query param instead: `wss://.../ws/conversations?token=...`
    Verified the same way dashboard_routes.py verifies the Authorization
    header — via auth.decode_access_token.
    """
    if token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    business_id = payload.get("business_id")
    if not business_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(business_id, websocket)
    try:
        while True:
            # Push-only from the server's side today — the dashboard
            # doesn't send anything over this socket. Still need to await
            # something so FastAPI keeps the connection open and detects
            # disconnects promptly; inbound frames are ignored.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(business_id, websocket)