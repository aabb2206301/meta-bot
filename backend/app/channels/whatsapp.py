"""
WhatsApp channel adapter (Meta Cloud API) — webhook receive + send().

See PROJECT_PLAN.md section 6 for the three things this file must get
right: verify X-Hub-Signature-256 before processing anything, ack 200
immediately and do the real work as a background task, and rely on the
UNIQUE(conversation_id, external_message_id) constraint (enforced in
orchestrator.py) to no-op retried deliveries.

Signature check, find-or-create customer/conversation, and the
background-task body are shared with instagram.py/facebook.py via
channels/common.py rather than duplicated here.
"""
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

from ..config import settings
from ..db.models import ChannelType
from .common import chunk_text, process_and_reply, verify_meta_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])

GRAPH_API_VERSION = "v20.0"
# WhatsApp's documented text-message body limit.
WHATSAPP_MAX_LEN = 4096


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    """Meta's one-time subscription handshake."""
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not verify_meta_signature(
        app_secret=settings.meta_app_secret, raw_body=raw_body, signature_header=signature_header
    ):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Signature verified — ack 200 no matter what we find inside; Meta
    # will retry indefinitely on anything else, including malformed
    # bodies, so we log and swallow parsing issues below instead.
    if not settings.business_id:
        logger.error("BUSINESS_ID is not configured — dropping WhatsApp webhook payload.")
        return Response(status_code=200)

    try:
        payload = await request.json()
    except ValueError:
        logger.warning("WhatsApp webhook: could not parse JSON body.")
        return Response(status_code=200)

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            # value.messages is absent for status callbacks (sent/
            # delivered/read receipts) — only "messages" events carry an
            # actual inbound customer message.
            messages = value.get("messages")
            if not messages:
                continue

            contacts = {
                c.get("wa_id"): c.get("profile", {}).get("name")
                for c in value.get("contacts", [])
            }

            for message in messages:
                if message.get("type") != "text":
                    # Non-text (image/audio/document/etc.) — out of
                    # scope for this bot; skip rather than error.
                    continue

                phone = message.get("from")
                text = message.get("text", {}).get("body", "")
                external_message_id = message.get("id")
                if not phone or not external_message_id:
                    continue

                background_tasks.add_task(
                    process_and_reply,
                    business_id=settings.business_id,
                    channel_field="phone",
                    external_id=phone,
                    customer_name=contacts.get(phone),
                    channel=ChannelType.whatsapp,
                    text=text,
                    external_message_id=external_message_id,
                    send=send,
                )

    return Response(status_code=200)


async def send(to_phone: str, text: str) -> None:
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        raise RuntimeError("WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID not configured.")

    url = (
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/"
        f"{settings.whatsapp_phone_number_id}/messages"
    )
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for chunk in chunk_text(text, WHATSAPP_MAX_LEN):
            resp = await client.post(
                url,
                headers=headers,
                json={
                    "messaging_product": "whatsapp",
                    "to": to_phone,
                    "type": "text",
                    "text": {"body": chunk},
                },
            )
            resp.raise_for_status()