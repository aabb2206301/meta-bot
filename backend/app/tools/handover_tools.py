"""
request_human_handover — flips conversation.status to 'handed_over' and
leaves a record staff can find. Actually pushing a live notification to
the dashboard is Phase 6's job (api/websocket.py); this function only
needs to leave the DB in a state the websocket layer can react to.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Conversation, ConversationStatus, Message, SenderType


async def request_human_handover(
    db: AsyncSession, *, conversation_id: str, args: dict
) -> dict:
    """
    conversation_id is injected by the orchestrator (trusted).
    args["reason"] is LLM-supplied.
    """
    reason = (args.get("reason") or "").strip()

    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    if conversation is None:
        return {"error": "conversation not found"}

    conversation.status = ConversationStatus.handed_over

    # Store the reason as a Message row so it's visible in the same
    # thread staff already read, rather than a separate column/table.
    handover_message = Message(
        conversation_id=conversation.id,
        sender=SenderType.bot,
        content=f"[handover] {reason}" if reason else "[handover] (no reason given)",
    )
    db.add(handover_message)

    await db.commit()
    await db.refresh(conversation)

    return {
        "conversation_id": str(conversation.id),
        "status": conversation.status.value,
    }