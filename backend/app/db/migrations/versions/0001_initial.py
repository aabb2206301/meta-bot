"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-18 17:30:00.000000

This is the first Alembic migration for the AI Sales Agent. It creates
the entire schema declared in `backend/app/db/models.py` (which mirrors
PROJECT_PLAN.md section 5).

IMPORTANT — run these against the target database BEFORE `alembic
upgrade head`:

    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

The pgvector extension is required for the `Product.embedding` and
`Faq.embedding` columns (vector(768)); uuid-ossp gives us
`uuid_generate_v4()` for the server-side default on PK columns. The
`pgvector/pgvector:pg16` image (see docker-compose.yml) has both
extensions available but does NOT enable them automatically.

NOTE on hand-writing: PROJECT_PLAN.md says to run
`alembic revision --autogenerate -m "initial schema"` and not hand-
write this. The sandbox this migration was drafted in doesn't have a
live Postgres, so it was written by hand against the models. The
output should match what autogenerate would produce; if you want to
verify, run `alembic revision --autogenerate -m "verify initial"`
against a fresh database and diff the result.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _create_enum_if_not_exists(name: str, values: list[str]) -> None:
    values_sql = ", ".join(f"'{v}'" for v in values)
    op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN
                CREATE TYPE {name} AS ENUM ({values_sql});
            END IF;
        END
        $$;
    """)


def upgrade() -> None:
    # ---- Enum types (create first; tables reference them via create_type=False) ----
    _create_enum_if_not_exists("channel_type", ["whatsapp", "instagram", "facebook"])
    _create_enum_if_not_exists("conversation_status", ["open", "handed_over", "closed"])
    _create_enum_if_not_exists("sender_type", ["customer", "bot", "staff"])
    _create_enum_if_not_exists("lead_status", ["new", "qualified", "hot", "lost", "converted"])
    _create_enum_if_not_exists("order_status", ["pending", "confirmed", "fulfilled", "cancelled"])
    _create_enum_if_not_exists("staff_role", ["owner", "agent"])

    # ---- businesses (root — no FKs) ----
    op.create_table(
        "businesses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ---- staff_users ----
    op.create_table(
        "staff_users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "agent", name="staff_role", create_type=False),
            nullable=False,
            server_default="agent",
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_staff_users_email"),
    )

    # ---- customers (3 unique constraints to prevent duplicate identities per channel) ----
    op.create_table(
        "customers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("name", sa.Text()),
        sa.Column("phone", sa.Text()),
        sa.Column("instagram_handle", sa.Text()),
        sa.Column("facebook_psid", sa.Text()),
        sa.Column("email", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("business_id", "phone", name="uq_customers_business_phone"),
        sa.UniqueConstraint("business_id", "instagram_handle", name="uq_customers_business_instagram"),
        sa.UniqueConstraint("business_id", "facebook_psid", name="uq_customers_business_facebook"),
    )

    # ---- products (embedding = vector(768); dimension must match
    #      settings.embedding_dimensions in app/config.py) ----
    op.create_table(
        "products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.Text()),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False, server_default="INR"),
        sa.Column("stock_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("image_url", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ---- faqs ----
    op.create_table(
        "faqs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("category", sa.Text()),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ---- conversations ----
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column(
            "channel",
            sa.Enum("whatsapp", "instagram", "facebook", name="channel_type", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("open", "handed_over", "closed", name="conversation_status", create_type=False),
            nullable=False,
            server_default="open",
        ),
        sa.Column("assigned_staff_id", UUID(as_uuid=True), sa.ForeignKey("staff_users.id")),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_message_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_conversations_customer", "conversations", ["customer_id"])
    op.create_index("idx_conversations_status", "conversations", ["status"])

    # ---- messages (UNIQUE (conversation_id, external_message_id) =
    #      the dedup key that stops Meta retried webhook deliveries from
    #      double-inserting, per PROJECT_PLAN.md section 6) ----
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column(
            "sender",
            sa.Enum("customer", "bot", "staff", name="sender_type", create_type=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text()),
        sa.Column("tool_calls", JSONB()),
        sa.Column("tool_results", JSONB()),
        sa.Column("external_message_id", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("conversation_id", "external_message_id", name="uq_messages_conversation_external"),
    )
    op.create_index("idx_messages_conversation_time", "messages", ["conversation_id", "created_at"])

    # ---- leads ----
    op.create_table(
        "leads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("new", "qualified", "hot", "lost", "converted", name="lead_status", create_type=False),
            nullable=False,
            server_default="new",
        ),
        sa.Column("score", sa.Integer(), server_default="0"),
        sa.Column("product_interest_id", UUID(as_uuid=True), sa.ForeignKey("products.id")),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_leads_status", "leads", ["status"])

    # ---- orders ----
    op.create_table(
        "orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id")),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "confirmed", "fulfilled", "cancelled", name="order_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("payment_method", sa.Text(), server_default="cod"),
        sa.Column("address", sa.Text()),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_orders_status", "orders", ["status"])

    # ---- order_items ----
    op.create_table(
        "order_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
    )

    # ---- kpi_daily_snapshot (date is VARCHAR — see db/models.py comment;
    #      query layer relies on ISO YYYY-MM-DD lexical ordering) ----
    op.create_table(
        "kpi_daily_snapshot",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("business_id", UUID(as_uuid=True), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "channel",
            sa.Enum("whatsapp", "instagram", "facebook", name="channel_type", create_type=False),
        ),
        sa.Column("enquiries_count", sa.Integer(), server_default="0"),
        sa.Column("ai_resolved_count", sa.Integer(), server_default="0"),
        sa.Column("avg_response_seconds", sa.Numeric(8, 2)),
        sa.Column("orders_count", sa.Integer(), server_default="0"),
        sa.Column("revenue", sa.Numeric(12, 2), server_default="0"),
        sa.UniqueConstraint("business_id", "date", "channel", name="uq_kpi_daily_business_date_channel"),
    )

    # ---- llm_call_log (cost / latency debugging data; doubles as the
    #      raw material for the "cost per conversation" KPI) ----
    op.create_table(
        "llm_call_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id")),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    # Drop in reverse dependency order. Indexes drop with their tables,
    # but listing them explicitly is harmless and makes the intent clear.
    op.drop_table("llm_call_log")
    op.drop_table("kpi_daily_snapshot")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("leads")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("faqs")
    op.drop_table("products")
    op.drop_table("customers")
    op.drop_table("staff_users")
    op.drop_table("businesses")

    op.execute("DROP TYPE IF EXISTS staff_role")
    op.execute("DROP TYPE IF EXISTS order_status")
    op.execute("DROP TYPE IF EXISTS lead_status")
    op.execute("DROP TYPE IF EXISTS sender_type")
    op.execute("DROP TYPE IF EXISTS conversation_status")
    op.execute("DROP TYPE IF EXISTS channel_type")
