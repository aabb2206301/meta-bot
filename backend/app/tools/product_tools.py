"""
search_products, check_stock — the only two tools that touch the
`products` table. The LLM never queries the DB directly; these functions
are the trusted boundary (see PROJECT_PLAN.md section 4).

business_id is injected by the orchestrator from the webhook's trusted
context, exactly like conversation_id in order_tools.create_order —
never accept it as an LLM argument.
"""
import logging
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Product
from ..embeddings.factory import get_embedding_provider

logger = logging.getLogger(__name__)

_RESULT_LIMIT = 5


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _serialize_product(product: Product) -> dict:
    return {
        "id": str(product.id),
        "name": product.name,
        "price": float(product.price),
        "currency": product.currency,
        "stock_qty": product.stock_qty,
    }


async def search_products(db: AsyncSession, *, business_id: str, args: dict) -> dict:
    """
    args["query"] comes from the LLM. Tries pgvector cosine-distance
    search first (if an embedding provider is configured); falls back to
    a plain ILIKE keyword search across name/description/category when
    no provider is available or the embedding call fails.
    """
    query = (args.get("query") or "").strip()
    if not query:
        return {"results": []}

    provider = get_embedding_provider()

    if provider is not None:
        try:
            query_embedding = await provider.embed(query)
            stmt = (
                select(Product)
                .where(Product.business_id == business_id)
                .where(Product.is_active.is_(True))
                .order_by(Product.embedding.cosine_distance(query_embedding))
                .limit(_RESULT_LIMIT)
            )
            result = await db.execute(stmt)
            products = result.scalars().all()
            return {"results": [_serialize_product(p) for p in products]}
        except Exception:
            logger.exception(
                "Embedding search failed for search_products — "
                "falling back to keyword search."
            )
            await db.rollback()

    # Fallback: plain Postgres ILIKE keyword search. No embedding
    # provider configured, or the vector search above raised.
    like_pattern = f"%{query}%"
    stmt = (
        select(Product)
        .where(Product.business_id == business_id)
        .where(Product.is_active.is_(True))
        .where(
            or_(
                Product.name.ilike(like_pattern),
                Product.description.ilike(like_pattern),
                Product.category.ilike(like_pattern),
            )
        )
        .limit(_RESULT_LIMIT)
    )
    result = await db.execute(stmt)
    products = result.scalars().all()
    return {"results": [_serialize_product(p) for p in products]}


async def check_stock(db: AsyncSession, *, business_id: str, args: dict) -> dict:
    """
    args["product_id"] comes from the LLM. Always scope by business_id —
    never trust product_id alone (same trust-boundary rule as
    order_tools.create_order).
    """
    raw_product_id = args.get("product_id")
    product_id = _parse_uuid(raw_product_id)
    if product_id is None:
        return {"error": "product_id is missing or not a valid id"}

    stmt = select(Product).where(
        Product.id == product_id, Product.business_id == business_id
    )
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()

    if product is None:
        return {"error": "product not found"}

    return {
        "product_id": str(product.id),
        "stock_qty": product.stock_qty,
        "is_active": product.is_active,
    }