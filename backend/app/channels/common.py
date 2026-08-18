"""
Shared helpers for the Meta channel webhooks (WhatsApp, Instagram, Facebook).

Factored out per PROJECT_PLAN.md section 6's suggestion, rather than
copy-pasting signature verification and the find-or-create/reply flow
across all three channel files:

- verify_meta_signature(): HMAC-SHA256 check of X-Hub-Signature-256
  against META_APP_SECRET — see "Verify webhook signatures".
- get_or_create_customer() / get_or_create_open_conversation(): resolve
  a channel-specific identifier (phone / instagram_handle /
  facebook_psid) into the Customer + Conversation rows the orchestrator
  needs.
- process_and_reply(): the actual background-task body — see "Meta
  expects a fast webhook ack, not a fast reply". Each channel's POST
  handler verifies the signature, returns 200 immediately, and schedules
  this as a BackgroundTasks job per inbound message.
- chunk_text(): splits an outbound reply to fit each channel's own max
  message length.

Duplicate webhook deliveries (Meta retries) are handled downstream by
orchestrator.handle_incoming_message via the
UNIQUE(conversation_id, external_message_id) constraint on `messages` —
nothing extra is needed here for that.
"""
import hashlib
import hmac
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import select

from ..bot.orchestrator import handle_incoming_message
from ..db.models import ChannelType, Conversation, ConversationStatus, Customer
from ..db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


def verify_meta_signature(
    *, app_secret: str | None, raw_body: bytes, signature_header: str | None
) -> bool:
    """
    Compares X-Hub-Signature-256 (format: 'sha256=<hex>') against an
    HMAC-SHA256 of the raw request body, keyed with META_APP_SECRET.
    Returns False (never raises) on any missing/malformed input so
    callers can uniformly 403 without a try/except.
    """
    if not app_secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


async def get_or_create_customer(
    db, *, business_id: str, channel_field: str, external_id: str, name: str | None = None
) -> Customer:
    """
    channel_field is the Customer column that holds this channel's
    identifier ('phone', 'instagram_handle', or 'facebook_psid') — see
    the per-channel UniqueConstraint(business_id, <field>) in
    db/models.py, which is what makes this lookup safe/idempotent.
    """
    stmt = select(Customer).where(
        Customer.business_id == business_id,
        getattr(Customer, channel_field) == external_id,
    )
    result = await db.execute(stmt)
    customer = result.scalar_one_or_none()
    if customer is not None:
        return customer

    customer = Customer(business_id=business_id, name=name, **{channel_field: external_id})
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


async def get_or_create_open_conversation(
    db, *, business_id: str, customer_id: str, channel: ChannelType
) -> Conversation:
    """
    Reuses the customer's existing non-closed conversation on this
    channel rather than starting a new thread per message — conversation
    history (orchestrator._load_history_messages) is scoped to one
    conversation, so a fresh row every message would reset context.
    """
    stmt = select(Conversation).where(
        Conversation.business_id == business_id,
        Conversation.customer_id == customer_id,
        Conversation.channel == channel,
        Conversation.status != ConversationStatus.closed,
    )
    result = await db.execute(stmt)
    conversation = result.scalars().first()
    if conversation is not None:
        return conversation

    conversation = Conversation(business_id=business_id, customer_id=customer_id, channel=channel)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


def chunk_text(text: str, max_len: int) -> list[str]:
    """Splits on whitespace boundaries where possible, so a long bot
    reply doesn't get sent as one oversized/rejected message."""
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_len:
        split_at = remaining.rfind(" ", 0, max_len)
        if split_at <= 0:
            split_at = max_len
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


async def process_and_reply(
    *,
    business_id: str,
    channel_field: str,
    external_id: str,
    customer_name: str | None,
    channel: ChannelType,
    text: str,
    external_message_id: str,
    send: Callable[[str, str], Awaitable[None]],
) -> None:
    """
    The background-task body shared by all three channels. Opens its own
    DB session — the request-scoped one from Depends(get_db) is gone by
    the time a background task actually runs — resolves customer +
    conversation, runs the bot loop, and sends whatever it replies with.

    `send` is the calling channel's own send(recipient_id, text)
    coroutine, passed in so this function stays channel-agnostic.
    """
    async with AsyncSessionLocal() as db:
        try:
            customer = await get_or_create_customer(
                db,
                business_id=business_id,
                channel_field=channel_field,
                external_id=external_id,
                name=customer_name,
            )
            conversation = await get_or_create_open_conversation(
                db, business_id=business_id, customer_id=str(customer.id), channel=channel
            )
            reply = await handle_incoming_message(
                db,
                conversation_id=str(conversation.id),
                customer_id=str(customer.id),
                business_id=business_id,
                channel=channel.value,
                text=text,
                external_message_id=external_message_id,
            )
        except Exception:  # noqa: BLE001 - a crashed background task must not
            # take the process down; log and give up on this one message.
            logger.exception(
                "Failed processing inbound %s message external_id=%s",
                channel.value,
                external_message_id,
            )
            return

    if not reply:
        # "" means _persist_customer_message found a duplicate webhook
        # delivery (see orchestrator.py) — nothing new to send.
        return

    try:
        await send(external_id, reply)
    except Exception:  # noqa: BLE001
        logger.exception("Failed sending %s reply to %s", channel.value, external_id)