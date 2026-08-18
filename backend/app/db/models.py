"""
SQLAlchemy models — direct translation of the schema in PROJECT_PLAN.md
section 5. Complete in the boilerplate: the schema has already been fully
designed in the plan, so there's no ambiguity left to resolve here. If you
change this file, mirror the change in a new Alembic migration (see
db/migrations/versions/).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pgvector not installed yet — embeddings columns will
    # fail at import time until `pip install pgvector` has been run.
    Vector = None  # type: ignore


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def now_col() -> Mapped[datetime]:
    return mapped_column(TIMESTAMP(timezone=True), server_default="now()")


class ChannelType(str, enum.Enum):
    whatsapp = "whatsapp"
    instagram = "instagram"
    facebook = "facebook"


class ConversationStatus(str, enum.Enum):
    open = "open"
    handed_over = "handed_over"
    closed = "closed"


class SenderType(str, enum.Enum):
    customer = "customer"
    bot = "bot"
    staff = "staff"


class LeadStatus(str, enum.Enum):
    new = "new"
    qualified = "qualified"
    hot = "hot"
    lost = "lost"
    converted = "converted"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    fulfilled = "fulfilled"
    cancelled = "cancelled"


class StaffRole(str, enum.Enum):
    owner = "owner"
    agent = "agent"


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = now_col()


class StaffUser(Base):
    __tablename__ = "staff_users"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[StaffRole] = mapped_column(
        SAEnum(StaffRole, name="staff_role"), nullable=False, default=StaffRole.agent
    )
    created_at: Mapped[datetime] = now_col()


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("business_id", "phone"),
        UniqueConstraint("business_id", "instagram_handle"),
        UniqueConstraint("business_id", "facebook_psid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    instagram_handle: Mapped[str | None] = mapped_column(Text)
    facebook_psid: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = now_col()


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="INR")
    stock_qty: Mapped[int] = mapped_column(default=0, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    # NOTE: dimension must match settings.embedding_dimensions (default 768
    # for Google's text-embedding-004). If you change embedding models,
    # update both this column and the migration.
    embedding = mapped_column(Vector(768), nullable=True) if Vector else None
    created_at: Mapped[datetime] = now_col()


class Faq(Base):
    __tablename__ = "faqs"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    embedding = mapped_column(Vector(768), nullable=True) if Vector else None
    created_at: Mapped[datetime] = now_col()


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    channel: Mapped[ChannelType] = mapped_column(SAEnum(ChannelType, name="channel_type"), nullable=False)
    status: Mapped[ConversationStatus] = mapped_column(
        SAEnum(ConversationStatus, name="conversation_status"),
        nullable=False,
        default=ConversationStatus.open,
    )
    assigned_staff_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staff_users.id"))
    started_at: Mapped[datetime] = now_col()
    last_message_at: Mapped[datetime] = now_col()

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("conversation_id", "external_message_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    sender: Mapped[SenderType] = mapped_column(SAEnum(SenderType, name="sender_type"), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    tool_calls: Mapped[dict | None] = mapped_column(JSONB)
    tool_results: Mapped[dict | None] = mapped_column(JSONB)
    external_message_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = now_col()

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    status: Mapped[LeadStatus] = mapped_column(
        SAEnum(LeadStatus, name="lead_status"), nullable=False, default=LeadStatus.new
    )
    score: Mapped[int | None] = mapped_column(default=0)
    product_interest_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = now_col()


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = uuid_pk()
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id"))
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, name="order_status"), nullable=False, default=OrderStatus.pending
    )
    payment_method: Mapped[str] = mapped_column(Text, default="cod")
    address: Mapped[str | None] = mapped_column(Text)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = now_col()

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")


class KpiDailySnapshot(Base):
    __tablename__ = "kpi_daily_snapshot"
    __table_args__ = (UniqueConstraint("business_id", "date", "channel"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False)
    date = mapped_column(String, nullable=False)  # DATE — kept simple; cast in queries
    channel: Mapped[ChannelType | None] = mapped_column(SAEnum(ChannelType, name="channel_type"))
    enquiries_count: Mapped[int | None] = mapped_column(default=0)
    ai_resolved_count: Mapped[int | None] = mapped_column(default=0)
    avg_response_seconds: Mapped[float | None] = mapped_column(Numeric(8, 2))
    orders_count: Mapped[int | None] = mapped_column(default=0)
    revenue: Mapped[float | None] = mapped_column(Numeric(12, 2), default=0)


class LlmCallLog(Base):
    __tablename__ = "llm_call_log"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversations.id"))
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    latency_ms: Mapped[int | None]
    created_at: Mapped[datetime] = now_col()
