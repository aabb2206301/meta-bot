"""
WhatsApp channel adapter (Meta Cloud API) — webhook receive + send().

>>> PHASE 5 TARGET — implement per PROJECT_PLAN.md section 6 <<<

TODO:
- APIRouter with two routes:
    GET  /webhooks/whatsapp   — Meta's verification handshake. Compare
        the `hub.verify_token` query param to settings.meta_verify_token;
        if it matches, return `hub.challenge` as plain text (200); else 403.
    POST /webhooks/whatsapp   — actual message delivery.
        1. Read the raw body BEFORE parsing JSON (needed for signature
           check).
        2. Verify `X-Hub-Signature-256` header against a HMAC-SHA256 of
           the raw body using settings.meta_app_secret. Reject (403) on
           mismatch — see PROJECT_PLAN.md section 6, "Verify webhook
           signatures".
        3. Return 200 OK IMMEDIATELY after signature check passes, then
           process the payload as a background task (FastAPI
           BackgroundTasks or asyncio.create_task) — see section 6,
           "Meta expects a fast webhook ack, not a fast reply". Do NOT
           call the LLM inside the request/response cycle.
        4. In the background task: parse Meta's payload shape into
           (customer phone, message text, external_message_id), find-or-
           create the Customer + Conversation rows, call
           bot.orchestrator.handle_incoming_message(...), then call
           send() below with the reply.
- async def send(to_phone: str, text: str) -> None:
    POST to Meta's Graph API `/v.../messages` endpoint using
    settings.whatsapp_access_token and settings.whatsapp_phone_number_id.
    Chunk `text` if it exceeds WhatsApp's message length limit.
- Register this router in main.py (Phase 6).
"""
from fastapi import APIRouter

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])


async def send(to_phone: str, text: str) -> None:
    raise NotImplementedError("Phase 5: implement WhatsApp send()")
