"""
Facebook Messenger channel adapter (Meta) — webhook receive + send().

Same handshake/signature/background-task pattern as whatsapp.py and
instagram.py; shared logic lives in channels/common.py. Payload shape is
the Messenger one: entry[].messaging[], keyed by the customer's PSID,
stored in customers.facebook_psid.
"""
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

from ..config import settings
from ..db.models import ChannelType
from .common import chunk_text, process_and_reply, verify_meta_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/facebook", tags=["facebook"])

GRAPH_API_VERSION = "v20.0"
# Meta's Send API text-message limit for Messenger-family products.
MESSENGER_MAX_LEN = 2000


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

    if not settings.business_id:
        logger.error("BUSINESS_ID is not configured — dropping Facebook webhook payload.")
        return Response(status_code=200)

    try:
        payload = await request.json()
    except ValueError:
        logger.warning("Facebook webhook: could not parse JSON body.")
        return Response(status_code=200)

    for entry in payload.get("entry", []):
        for messaging_event in entry.get("messaging", []):
            message = messaging_event.get("message")
            if not message or message.get("is_echo"):
                # is_echo events confirm our own send() calls — not a
                # new customer message; skip to avoid replying to self.
                continue

            text = message.get("text")
            if not text:
                # Attachment-only messages — out of scope for this bot.
                continue

            sender = messaging_event.get("sender", {})
            psid = sender.get("id")
            external_message_id = message.get("mid")
            if not psid or not external_message_id:
                continue

            background_tasks.add_task(
                process_and_reply,
                business_id=settings.business_id,
                channel_field="facebook_psid",
                external_id=psid,
                customer_name=None,
                channel=ChannelType.facebook,
                text=text,
                external_message_id=external_message_id,
                send=send,
            )

    return Response(status_code=200)


async def send(psid: str, text: str) -> None:
    if not settings.facebook_page_access_token:
        raise RuntimeError("FACEBOOK_PAGE_ACCESS_TOKEN not configured.")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    params = {"access_token": settings.facebook_page_access_token}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for chunk in chunk_text(text, MESSENGER_MAX_LEN):
            resp = await client.post(
                url,
                params=params,
                json={"recipient": {"id": psid}, "message": {"text": chunk}},
            )
            resp.raise_for_status()