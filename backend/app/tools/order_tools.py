"""
create_order, update_order_status — the only two tools that write to
`orders` / `order_items`.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Conversation, Order, OrderItem, OrderStatus, Product


def _parse_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


async def create_order(db: AsyncSession, *, conversation_id: str, args: dict) -> dict:
    """
    conversation_id comes from the webhook context, injected by the
    orchestrator — NEVER from the LLM's arguments. Only product_id,
    quantity, address, payment_method are LLM-supplied. This boundary
    matters: if you let the model supply conversation_id or customer_id,
    a manipulated conversation could write orders against someone else's
    account. Content parameters from the LLM, identity parameters from
    your own trusted context — always.
    """
    conv_stmt = select(Conversation).where(Conversation.id == conversation_id)
    conv_result = await db.execute(conv_stmt)
    conversation = conv_result.scalar_one_or_none()
    if conversation is None:
        return {"error": "conversation not found"}

    product_id = _parse_uuid(args.get("product_id"))
    quantity = args.get("quantity")
    address = args.get("address")
    payment_method = args.get("payment_method", "cod")

    if product_id is None:
        return {"error": "product_id is missing or not a valid id"}
    if not isinstance(quantity, int) or quantity <= 0:
        return {"error": "quantity must be a positive integer"}
    if not address:
        return {"error": "address is required"}

    # Re-check stock at write time using the same product_id/business_id
    # scoping check_stock uses — never trust a stale stock figure the LLM
    # may have seen earlier in the conversation.
    product_stmt = select(Product).where(
        Product.id == product_id,
        Product.business_id == conversation.business_id,
    )
    product_result = await db.execute(product_stmt)
    product = product_result.scalar_one_or_none()

    if product is None:
        return {"error": "product not found"}
    if not product.is_active:
        return {"error": "product is not currently available"}
    if product.stock_qty < quantity:
        return {
            "error": f"insufficient stock: only {product.stock_qty} left",
            "stock_qty": product.stock_qty,
        }

    order = Order(
        customer_id=conversation.customer_id,
        status=OrderStatus.pending,
        payment_method=payment_method,
        address=address,
        total_amount=product.price * quantity,
    )
    db.add(order)
    await db.flush()  # populate order.id for the OrderItem FK, same transaction

    order_item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=quantity,
        unit_price=product.price,
    )
    db.add(order_item)

    # Decrement stock in the same transaction as the order/order_item
    # inserts — all three commit together or not at all.
    product.stock_qty -= quantity

    await db.commit()
    await db.refresh(order)

    return {"order_id": str(order.id), "status": order.status.value}


async def update_order_status(db: AsyncSession, *, customer_id: str, args: dict) -> dict:
    """
    args: order_id, status (both LLM-supplied). customer_id is injected
    by the orchestrator from trusted context. Before allowing the
    update, verify order.customer_id == customer_id — the same
    trust-boundary rule as create_order, applied to reads instead of
    writes. Without this check a manipulated conversation could cancel
    or alter someone else's order by guessing/stating an order_id.
    """
    order_id = _parse_uuid(args.get("order_id"))
    status_str = args.get("status")

    if order_id is None:
        return {"error": "order_id is missing or not a valid id"}
    if not status_str:
        return {"error": "status is required"}

    try:
        status = OrderStatus(status_str)
    except ValueError:
        return {
            "error": f"invalid status '{status_str}'. "
            f"Must be one of: {[s.value for s in OrderStatus]}"
        }

    stmt = select(Order).where(Order.id == order_id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()

    # Deliberately return the same "not found" error whether the order
    # doesn't exist or belongs to someone else — don't leak which case
    # it is to the LLM/customer.
    if order is None or str(order.customer_id) != str(customer_id):
        return {"error": "order not found"}

    order.status = status
    order.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(order)

    return {"order_id": str(order.id), "status": order.status.value}