"""
REST endpoints the React dashboard reads from: KPIs, conversations,
orders, products (and staff auth).

Implemented per PROJECT_PLAN.md sections 1-2 & 5.

All routes except /api/auth/login require a valid JWT (see .auth) and
scope every query by the business_id encoded in that JWT — the same
trusted-identity boundary tools/order_tools.py applies to the bot,
applied here to staff.
"""
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import (
    ChannelType,
    Conversation,
    ConversationStatus,
    Customer,
    KpiDailySnapshot,
    Message,
    SenderType,  # Phase 9: added for POST /api/conversations/{id}/messages
    Order,
    OrderItem,
    OrderStatus,
    Product,
    StaffUser,
)
from ..db.session import get_db
from .auth import create_access_token, get_current_staff, verify_password
from .websocket import broadcast_new_message  # Phase 9: added for staff-reply push

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["dashboard"])

DEFAULT_KPI_WINDOW_DAYS = 30


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        return None


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(StaffUser).where(StaffUser.email == body.email)
    staff_user = (await db.execute(stmt)).scalar_one_or_none()

    # Same response whether the email doesn't exist or the password is
    # wrong — don't leak which case it is.
    if staff_user is None or not verify_password(body.password, staff_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    token = create_access_token(
        staff_id=str(staff_user.id),
        business_id=str(staff_user.business_id),
        role=staff_user.role.value,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expire_minutes * 60,
        "staff": {
            "id": str(staff_user.id),
            "name": staff_user.name,
            "email": staff_user.email,
            "role": staff_user.role.value,
        },
    }


# ---------------------------------------------------------------------
# KPIs — powers Dashboard.tsx (Phase 9)
# ---------------------------------------------------------------------


@router.get("/kpis/summary")
async def get_kpi_summary(
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    channel: ChannelType | None = Query(None),
    staff: dict = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    business_id = staff["business_id"]
    # kpi_daily_snapshot.date is stored as a plain string column (see
    # db/models.py comment: "DATE — kept simple; cast in queries"), but
    # since it's always written as ISO YYYY-MM-DD, lexical string
    # comparison sorts/filters identically to a real date column.
    to_date = to or date.today().isoformat()
    from_date = from_ or (date.today() - timedelta(days=DEFAULT_KPI_WINDOW_DAYS)).isoformat()

    conditions = [
        KpiDailySnapshot.business_id == business_id,
        KpiDailySnapshot.date >= from_date,
        KpiDailySnapshot.date <= to_date,
    ]
    if channel is not None:
        conditions.append(KpiDailySnapshot.channel == channel)

    totals_stmt = select(
        func.coalesce(func.sum(KpiDailySnapshot.enquiries_count), 0),
        func.coalesce(func.sum(KpiDailySnapshot.ai_resolved_count), 0),
        func.avg(KpiDailySnapshot.avg_response_seconds),
        func.coalesce(func.sum(KpiDailySnapshot.orders_count), 0),
        func.coalesce(func.sum(KpiDailySnapshot.revenue), 0),
    ).where(*conditions)
    totals = (await db.execute(totals_stmt)).one()

    # Grouped by date (summed across channels unless a channel filter
    # narrowed it already) so Dashboard.tsx can drive a trend chart
    # without aggregating raw rows client-side.
    daily_stmt = (
        select(
            KpiDailySnapshot.date,
            func.coalesce(func.sum(KpiDailySnapshot.enquiries_count), 0),
            func.coalesce(func.sum(KpiDailySnapshot.ai_resolved_count), 0),
            func.coalesce(func.sum(KpiDailySnapshot.orders_count), 0),
            func.coalesce(func.sum(KpiDailySnapshot.revenue), 0),
        )
        .where(*conditions)
        .group_by(KpiDailySnapshot.date)
        .order_by(KpiDailySnapshot.date)
    )
    daily_rows = (await db.execute(daily_stmt)).all()

    return {
        "from": from_date,
        "to": to_date,
        "channel": channel.value if channel else None,
        "summary": {
            "enquiries_count": totals[0],
            "ai_resolved_count": totals[1],
            "avg_response_seconds": float(totals[2]) if totals[2] is not None else None,
            "orders_count": totals[3],
            "revenue": float(totals[4]),
        },
        "daily": [
            {
                "date": row[0],
                "enquiries_count": row[1],
                "ai_resolved_count": row[2],
                "orders_count": row[3],
                "revenue": float(row[4]),
            }
            for row in daily_rows
        ],
    }


# ---------------------------------------------------------------------
# Conversations — powers Conversations.tsx (Phase 9)
# ---------------------------------------------------------------------


@router.get("/conversations")
async def list_conversations(
    status_filter: ConversationStatus | None = Query(None, alias="status"),
    channel: ChannelType | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    staff: dict = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    business_id = staff["business_id"]
    conditions = [Conversation.business_id == business_id]
    if status_filter is not None:
        conditions.append(Conversation.status == status_filter)
    if channel is not None:
        conditions.append(Conversation.channel == channel)

    total = (
        await db.execute(select(func.count()).select_from(Conversation).where(*conditions))
    ).scalar_one()

    stmt = (
        select(Conversation, Customer.name)
        .join(Customer, Customer.id == Conversation.customer_id)
        .where(*conditions)
        .order_by(Conversation.last_message_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": str(conv.id),
                "customer_name": customer_name,
                "channel": conv.channel.value,
                "status": conv.status.value,
                "assigned_staff_id": (
                    str(conv.assigned_staff_id) if conv.assigned_staff_id else None
                ),
                "started_at": conv.started_at.isoformat(),
                "last_message_at": conv.last_message_at.isoformat(),
            }
            for conv, customer_name in rows
        ],
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    staff: dict = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    conv_uuid = _parse_uuid(conversation_id)
    if conv_uuid is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    conv_stmt = select(Conversation).where(
        Conversation.id == conv_uuid,
        Conversation.business_id == staff["business_id"],
    )
    conversation = (await db.execute(conv_stmt)).scalar_one_or_none()
    if conversation is None:
        # Same "not found" whether it's genuinely missing or belongs to
        # another business — same non-leaking principle as
        # tools/order_tools.py:update_order_status.
        raise HTTPException(status_code=404, detail="conversation not found")

    stmt = (
        select(Message)
        .where(Message.conversation_id == conv_uuid)
        .order_by(Message.created_at.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "conversation_id": str(conversation.id),
        "status": conversation.status.value,
        "messages": [
            {
                "id": str(m.id),
                "sender": m.sender.value,
                "content": m.content,
                "tool_calls": m.tool_calls,
                "tool_results": m.tool_results,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ],
    }


# ---------------------------------------------------------------------
# Staff message — added in Phase 9
# ---------------------------------------------------------------------


class StaffMessageCreate(BaseModel):
    content: str


@router.post("/conversations/{conversation_id}/messages", status_code=status.HTTP_201_CREATED)
async def post_staff_message(
    conversation_id: str,
    body: StaffMessageCreate,
    staff: dict = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    """
    Staff-authored reply. Persists a Message row with sender='staff',
    bumps the conversation's last_message_at, and broadcasts over the
    dashboard websocket so other staff viewing this conversation see
    the new message live.

    Trust boundary: business_id comes from the JWT — same pattern as
    every other staff endpoint in this file. The conversation is
    scoped by joining through Customer.business_id; mismatched or
    missing rows surface as a 404 without revealing whether the
    conversation exists under a different business.

    KNOWN LIMITATION (Phase 9 scope): this persists the message and
    fans it out to dashboards, but does NOT send the message out to
    the originating channel (WhatsApp / Instagram / Facebook). For a
    full staff-reply path, this endpoint would also dispatch via
    channels/{channel}.py:send() using the conversation's channel and
    the customer's external ID. Deferred per Phase 9's plan note:
    "post through whatever endpoint Phase 6 exposes ... add one in
    this phase if it wasn't included in Phase 6".
    """
    conv_uuid = _parse_uuid(conversation_id)
    if conv_uuid is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    stmt = (
        select(Conversation, Customer)
        .join(Customer, Customer.id == Conversation.customer_id)
        .where(Conversation.id == conv_uuid)
    )
    row = (await db.execute(stmt)).first()
    if row is None or str(row[1].business_id) != staff["business_id"]:
        raise HTTPException(status_code=404, detail="conversation not found")

    conversation = row[0]
    msg = Message(
        conversation_id=conv_uuid,
        sender=SenderType.STAFF,
        content=body.content,
    )
    db.add(msg)
    conversation.last_message_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)

    # Broadcast so any other staff dashboards viewing this conversation
    # pick the new message up live. The sender's own dashboard will see
    # a brief duplicate (its own optimistic append + this WS event);
    # Conversations.tsx dedupes on (sender, content, recent).
    await broadcast_new_message(
        business_id=staff["business_id"],
        conversation_id=str(conv_uuid),
        text=body.content,
    )

    return {
        "id": str(msg.id),
        "sender": msg.sender.value,
        "content": msg.content,
        "created_at": msg.created_at.isoformat(),
    }


# ---------------------------------------------------------------------
# Orders — powers Orders.tsx (Phase 10)
# ---------------------------------------------------------------------


@router.get("/orders")
async def list_orders(
    status_filter: OrderStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    staff: dict = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    business_id = staff["business_id"]
    # orders has no business_id column of its own — scope through its
    # customer, same as tools/order_tools.py implicitly does by trusting
    # the order's customer_id.
    conditions = [Customer.business_id == business_id]
    if status_filter is not None:
        conditions.append(Order.status == status_filter)

    total = (
        await db.execute(
            select(func.count())
            .select_from(Order)
            .join(Customer, Customer.id == Order.customer_id)
            .where(*conditions)
        )
    ).scalar_one()

    stmt = (
        select(Order, Customer.name)
        .join(Customer, Customer.id == Order.customer_id)
        .where(*conditions)
        .order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    order_ids = [order.id for order, _ in rows]

    items_by_order: dict[uuid.UUID, list[dict]] = {}
    if order_ids:
        items_stmt = (
            select(OrderItem, Product.name)
            .join(Product, Product.id == OrderItem.product_id)
            .where(OrderItem.order_id.in_(order_ids))
        )
        for item, product_name in (await db.execute(items_stmt)).all():
            items_by_order.setdefault(item.order_id, []).append(
                {
                    "product_id": str(item.product_id),
                    "product_name": product_name,
                    "quantity": item.quantity,
                    "unit_price": float(item.unit_price),
                }
            )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": str(order.id),
                "customer_name": customer_name,
                "status": order.status.value,
                "payment_method": order.payment_method,
                "address": order.address,
                "total_amount": float(order.total_amount),
                "items": items_by_order.get(order.id, []),
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
            }
            for order, customer_name in rows
        ],
    }


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


@router.patch("/orders/{order_id}")
async def update_order_status_staff(
    order_id: str,
    body: OrderStatusUpdate,
    staff: dict = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    """
    Staff/manual path — separate from the bot's
    tools/order_tools.py:update_order_status, but writes the same
    columns. The trust boundary here is business_id (via the order's
    customer), not customer_id, since the caller is staff acting for the
    whole business rather than a bot acting for one customer.
    """
    order_uuid = _parse_uuid(order_id)
    if order_uuid is None:
        raise HTTPException(status_code=404, detail="order not found")

    stmt = (
        select(Order)
        .join(Customer, Customer.id == Order.customer_id)
        .where(Order.id == order_uuid, Customer.business_id == staff["business_id"])
    )
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="order not found")

    order.status = body.status
    order.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(order)

    return {"id": str(order.id), "status": order.status.value}


# ---------------------------------------------------------------------
# Products — powers Products.tsx (Phase 10)
# ---------------------------------------------------------------------


def _product_to_dict(p: Product) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "category": p.category,
        "price": float(p.price),
        "currency": p.currency,
        "stock_qty": p.stock_qty,
        "image_url": p.image_url,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat(),
    }


@router.get("/products")
async def list_products(
    category: str | None = Query(None),
    is_active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    staff: dict = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    business_id = staff["business_id"]
    conditions = [Product.business_id == business_id]
    if category is not None:
        conditions.append(Product.category == category)
    if is_active is not None:
        conditions.append(Product.is_active == is_active)

    total = (
        await db.execute(select(func.count()).select_from(Product).where(*conditions))
    ).scalar_one()

    stmt = (
        select(Product)
        .where(*conditions)
        .order_by(Product.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_product_to_dict(p) for p in rows],
    }


class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None
    price: float
    currency: str = "INR"
    stock_qty: int = 0
    image_url: str | None = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    price: float | None = None
    currency: str | None = None
    stock_qty: int | None = None
    image_url: str | None = None
    is_active: bool | None = None


@router.post("/products", status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    staff: dict = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    # business_id comes from the staff member's own JWT, never from the
    # request body — same trust-boundary rule as everywhere else here.
    product = Product(business_id=staff["business_id"], **body.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return _product_to_dict(product)


@router.patch("/products/{product_id}")
async def update_product(
    product_id: str,
    body: ProductUpdate,
    staff: dict = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    product_uuid = _parse_uuid(product_id)
    if product_uuid is None:
        raise HTTPException(status_code=404, detail="product not found")

    stmt = select(Product).where(
        Product.id == product_uuid, Product.business_id == staff["business_id"]
    )
    product = (await db.execute(stmt)).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")

    changes = body.model_dump(exclude_unset=True)
    stale_fields = {"price", "stock_qty", "description"} & changes.keys()
    if stale_fields and product.embedding is not None:
        # KNOWN LIMITATION (see PROJECT_PLAN.md section 1 / this file's
        # original TODO): changing price/stock/description leaves
        # `embedding` stale. Re-embedding on save would mean calling
        # embeddings/factory.py here; deferred for now per the plan's
        # "accept staleness, note it" option — at minimum this logs it
        # instead of silently serving a stale vector unflagged.
        logger.warning(
            "Product %s updated with fields %s — its embedding is now stale "
            "(re-embed-on-save not implemented).",
            product.id,
            stale_fields,
        )

    for field, value in changes.items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)
    return _product_to_dict(product)
