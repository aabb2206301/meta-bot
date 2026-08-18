"""
upsert_lead — create or update the lead row for the current conversation.

conversation_id and customer_id are injected by the orchestrator from
trusted webhook context — NEVER from LLM arguments (same trust boundary
as order_tools.create_order). args contains LLM-supplied content only:
status, product_interest_id, notes.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Lead, LeadStatus


def _parse_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


async def upsert_lead(
    db: AsyncSession, *, conversation_id: str, customer_id: str, args: dict
) -> dict:
    status_str = args.get("status")
    if not status_str:
        return {"error": "status is required"}

    try:
        status = LeadStatus(status_str)
    except ValueError:
        return {
            "error": f"invalid status '{status_str}'. "
            f"Must be one of: {[s.value for s in LeadStatus]}"
        }

    product_interest_id = None
    if "product_interest_id" in args and args["product_interest_id"]:
        product_interest_id = _parse_uuid(args["product_interest_id"])
        if product_interest_id is None:
            return {"error": "product_interest_id is not a valid id"}

    stmt = select(Lead).where(Lead.conversation_id == conversation_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if lead is not None:
        lead.status = status
        if "product_interest_id" in args:
            lead.product_interest_id = product_interest_id
        if "notes" in args:
            lead.notes = args.get("notes")
        lead.updated_at = datetime.now(timezone.utc)
    else:
        lead = Lead(
            conversation_id=conversation_id,
            customer_id=customer_id,
            status=status,
            product_interest_id=product_interest_id,
            notes=args.get("notes"),
        )
        db.add(lead)

    await db.commit()
    await db.refresh(lead)

    return {"lead_id": str(lead.id), "status": lead.status.value}