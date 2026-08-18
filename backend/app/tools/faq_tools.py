"""
search_faqs — same pattern as search_products but against the `faqs`
table (see product_tools.py for the embedding-vs-keyword-search decision
this mirrors).

NOTE: the "embed, or fall back to ILIKE" logic here is intentionally
duplicated from product_tools.py rather than factored into a shared
helper. Both files are short and the query shapes differ slightly
(different columns, different result limit), so duplication seemed
clearer than a shared abstraction for two call sites — revisit if a
third semantic-search consumer shows up.
"""
import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Faq
from ..embeddings.factory import get_embedding_provider

logger = logging.getLogger(__name__)

_RESULT_LIMIT = 3


def _serialize_faq(faq: Faq) -> dict:
    return {"question": faq.question, "answer": faq.answer}


async def search_faqs(db: AsyncSession, *, business_id: str, args: dict) -> dict:
    """
    args["query"] comes from the LLM. business_id is injected by the
    orchestrator from trusted webhook context — never accept it as an
    LLM argument.
    """
    query = (args.get("query") or "").strip()
    if not query:
        return {"results": []}

    provider = get_embedding_provider()

    if provider is not None:
        try:
            query_embedding = await provider.embed(query)
            stmt = (
                select(Faq)
                .where(Faq.business_id == business_id)
                .order_by(Faq.embedding.cosine_distance(query_embedding))
                .limit(_RESULT_LIMIT)
            )
            result = await db.execute(stmt)
            faqs = result.scalars().all()
            return {"results": [_serialize_faq(f) for f in faqs]}
        except Exception:
            logger.exception(
                "Embedding search failed for search_faqs — falling back "
                "to keyword search."
            )
            await db.rollback()

    # Fallback: plain Postgres ILIKE keyword search across question/
    # answer/category.
    like_pattern = f"%{query}%"
    stmt = (
        select(Faq)
        .where(Faq.business_id == business_id)
        .where(
            or_(
                Faq.question.ilike(like_pattern),
                Faq.answer.ilike(like_pattern),
                Faq.category.ilike(like_pattern),
            )
        )
        .limit(_RESULT_LIMIT)
    )
    result = await db.execute(stmt)
    faqs = result.scalars().all()
    return {"results": [_serialize_faq(f) for f in faqs]}