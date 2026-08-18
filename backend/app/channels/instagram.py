"""
Instagram channel adapter (Meta Messaging API for Instagram) — webhook
receive + send().

Same handshake/signature/background-task pattern as whatsapp.py; the
shared logic lives in channels/common.py. Payload shape differs from
WhatsApp's — Instagram (like Facebook Messenger) delivers events under
entry[].messaging[], keyed by the customer's IG-scoped sender id, which
is stored in customers.instagram_handle (despite the column name — see
db/models.py).
"""
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

from ..config import settings
from ..db.models import ChannelType
from .common import chunk_text, process_and_reply, verify_meta_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/instagram", tags=["instagram"])

GRAPH_API_VERSION = "v20.0"
# Meta's Send API text-message limit for Messenger-family products.
INSTAGRAM_MAX_LEN = 2000


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
        logger.error("BUSINESS_ID is not configured — dropping Instagram webhook payload.")
        return Response(status_code=200)

    try:
        payload = await request.json()
    except ValueError:
        logger.warning("Instagram webhook: could not parse JSON body.")
        return Response(status_code=200)

    for entry in payload.get("entry", []):
        for messaging_event in entry.get("messaging", []):
            message = messaging_event.get("message")
            if not message or message.get("is_echo"):
                # is_echo events are Meta confirming our own outbound
                # send() calls being delivered — not a new customer
                # message; skip to avoid the bot replying to itself.
                continue

            text = message.get("text")
            if not text:
                # Attachment-only messages (image/sticker/etc.) — out of
                # scope for this bot.
                continue

            sender = messaging_event.get("sender", {})
            ig_scoped_id = sender.get("id")
            external_message_id = message.get("mid")
            if not ig_scoped_id or not external_message_id:
                continue

            background_tasks.add_task(
                process_and_reply,
                business_id=settings.business_id,
                channel_field="instagram_handle",
                external_id=ig_scoped_id,
                customer_name=None,
                channel=ChannelType.instagram,
                text=text,
                external_message_id=external_message_id,
                send=send,
            )

    return Response(status_code=200)


async def send(recipient_id: str, text: str) -> None:
    if not settings.instagram_page_access_token:
        raise RuntimeError("INSTAGRAM_PAGE_ACCESS_TOKEN not configured.")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    params = {"access_token": settings.instagram_page_access_token}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for chunk in chunk_text(text, INSTAGRAM_MAX_LEN):
            resp = await client.post(
                url,
                params=params,
                json={"recipient": {"id": recipient_id}, "message": {"text": chunk}},
            )
            resp.raise_for_status()