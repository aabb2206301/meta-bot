"""
Faker-based historical data generator — populates a business with
plausible customers, conversations, messages, leads, orders, products,
FAQs, and backfills kpi_daily_snapshot so the dashboard has something to
show on day one instead of an empty state.

Run with:
    python -m app.seed.seed_data

WHAT THIS SCRIPT DOES
----------------------
1. Creates one Business row (its id is printed at the end — copy it into
   .env as BUSINESS_ID).
2. Creates one StaffUser (role=owner) so you can log into the dashboard.
   NOTE: this account is *not* part of the original TODO list in
   PROJECT_PLAN.md section 2 — it was added on request because Phase 6's
   dashboard requires a JWT login and there's otherwise no way to sign
   in after seeding. Its password is hashed with raw `bcrypt`
   (bcrypt.hashpw / bcrypt.checkpw) to match the Phase 6 login endpoint.
   `bcrypt` needs to be added to requirements.txt (not present in the
   original pinned list) — see the accompanying requirements.txt diff.
3. Creates NUM_PRODUCTS products across a small set of generic
   categories (edit CATEGORIES below to fit a real niche later).
4. Creates NUM_FAQS faqs (shipping/returns/payment/general).
5. Creates NUM_CUSTOMERS customers spread across the three channels.
6. Creates conversations + messages over the last DAYS_BACK days,
   weighted so recent days have more volume than older ones.
7. Creates leads (subset of conversations) and orders (subset of leads),
   with order_items referencing real products/prices.
8. Aggregates everything generated above (in-memory, not via extra
   queries) into kpi_daily_snapshot rows — one row per (date, channel)
   for the full 60-day window, including zero-activity days, so trend
   charts render a continuous line instead of gaps.

KNOWN LIMITATIONS (called out per the plan)
--------------------------------------------
- `embedding` columns on Product/Faq are left NULL. Seeding real
  embeddings would burn API quota on every run; product/faq search
  will fall back to keyword search (ILIKE / full-text) for these rows
  until a separate backfill script populates embeddings.
- `llm_call_log` is intentionally NOT seeded — it wasn't in the
  original TODO list for this phase, and the table is naturally
  populated once the orchestrator (Phase 4) starts running for real.
  If you want historical cost/latency data for demo purposes, that
  would be a deliberate follow-up, not something this script assumes.
- IDs are generated client-side (uuid.uuid4()) rather than left to
  server-side defaults, purely so FK references can be wired up in
  Python before the INSERTs happen. SQLAlchemy sorts the flush order
  by table FK dependency automatically, so a single `session.add_all`
  + one commit is enough — no manual flush ordering needed.
"""
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from faker import Faker

from ..db.models import (
    Business,
    ChannelType,
    Conversation,
    ConversationStatus,
    Customer,
    Faq,
    KpiDailySnapshot,
    Lead,
    LeadStatus,
    LlmCallLog,  # noqa: F401  (imported for clarity that it's intentionally unused)
    Message,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    SenderType,
    StaffRole,
    StaffUser,
)
from ..db.session import AsyncSessionLocal

fake = Faker()

# --- Tunables -----------------------------------------------------------
NUM_PRODUCTS = 16
NUM_FAQS = 8
NUM_CUSTOMERS = 40
NUM_CONVERSATIONS = 70          # spread across customers (some get >1)
DAYS_BACK = 60
BUSINESS_NAME = "Demo Storefront"

OWNER_EMAIL = "owner@demo-storefront.test"
OWNER_PASSWORD = "ChangeMe123!"  # printed at the end — rotate after first login

CHANNELS = [ChannelType.whatsapp, ChannelType.instagram, ChannelType.facebook]

# Generic, editable product taxonomy — swap this out for a real catalog later.
CATEGORIES: dict[str, list[str]] = {
    "Apparel": ["Cotton T-Shirt", "Denim Jacket", "Running Shorts", "Wool Sweater", "Linen Shirt"],
    "Electronics": ["Wireless Earbuds", "Bluetooth Speaker", "Power Bank", "Smart Watch", "USB-C Hub"],
    "Home & Kitchen": ["Ceramic Mug Set", "Non-Stick Pan", "Table Lamp", "Storage Basket", "Cutting Board"],
    "Beauty & Personal Care": ["Face Serum", "Herbal Shampoo", "Lip Balm Set", "Sunscreen SPF50"],
    "Accessories": ["Leather Wallet", "Canvas Tote Bag", "Sunglasses", "Analog Watch"],
}

FAQ_SEED = [
    ("What payment methods do you accept?", "We currently accept Cash on Delivery (COD) only.", "payment"),
    ("How long does shipping take?", "Orders are typically delivered within 3-5 business days.", "shipping"),
    ("Do you ship internationally?", "At the moment we only ship within the country.", "shipping"),
    ("What is your return policy?", "Items can be returned within 7 days of delivery if unused and in original packaging.", "returns"),
    ("How do I track my order?", "Once your order is confirmed, our team will share tracking details over chat.", "shipping"),
    ("Can I cancel my order?", "Orders can be cancelled any time before they are marked as fulfilled.", "orders"),
    ("Do you offer cash refunds?", "Refunds for cancelled or returned COD orders are processed as store credit.", "returns"),
    ("Is there a minimum order value?", "No, there is no minimum order value.", "orders"),
]

TOOL_SAMPLES = [
    {
        "tool_calls": [{"id": "call_1", "name": "search_products", "arguments": {"query": "wireless earbuds"}}],
        "tool_results": [{"id": "call_1", "result": {"matches": 3}}],
    },
    {
        "tool_calls": [{"id": "call_1", "name": "search_faqs", "arguments": {"query": "return policy"}}],
        "tool_results": [{"id": "call_1", "result": {"matches": 1}}],
    },
    {
        "tool_calls": [{"id": "call_1", "name": "upsert_lead", "arguments": {"status": "qualified"}}],
        "tool_results": [{"id": "call_1", "result": {"ok": True}}],
    },
]

now = datetime.now(timezone.utc)


def weighted_day_offset() -> int:
    """Recent days weighted higher: day 0 (today) has weight DAYS_BACK,
    day DAYS_BACK-1 has weight 1."""
    days = list(range(DAYS_BACK))
    weights = [DAYS_BACK - d for d in days]
    return random.choices(days, weights=weights, k=1)[0]


def random_timestamp_on_day(day_offset: int) -> datetime:
    base = now - timedelta(days=day_offset)
    return base.replace(
        hour=random.randint(8, 22),
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        microsecond=0,
    )


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        try:
            objects: list = []
            kpi = {}  # (date_str, channel) -> dict of running aggregates

            def kpi_bucket(date_str: str, channel: ChannelType) -> dict:
                key = (date_str, channel)
                if key not in kpi:
                    kpi[key] = {
                        "enquiries_count": 0,
                        "ai_resolved_count": 0,
                        "response_seconds": [],
                        "orders_count": 0,
                        "revenue": 0.0,
                    }
                return kpi[key]

            # Pre-seed every (date, channel) combo with zeroed buckets so the
            # dashboard's trend charts get a continuous 60-day line, not gaps.
            for d in range(DAYS_BACK):
                date_str = (now - timedelta(days=d)).date().isoformat()
                for ch in CHANNELS:
                    kpi_bucket(date_str, ch)

            # --- 1. Business ------------------------------------------------
            business = Business(id=uuid.uuid4(), name=BUSINESS_NAME, created_at=now)
            objects.append(business)

            # --- 2. Staff (owner) --------------------------------------------
            owner = StaffUser(
                id=uuid.uuid4(),
                business_id=business.id,
                name="Store Owner",
                email=OWNER_EMAIL,
                password_hash=hash_password(OWNER_PASSWORD),
                role=StaffRole.owner,
                created_at=now,
            )
            objects.append(owner)

            # --- 3. Products ---------------------------------------------------
            products: list[Product] = []
            for _ in range(NUM_PRODUCTS):
                category = random.choice(list(CATEGORIES.keys()))
                base_name = random.choice(CATEGORIES[category])
                name = f"{fake.word().capitalize()} {base_name}"
                price = round(random.uniform(199, 4999), 2)
                product = Product(
                    id=uuid.uuid4(),
                    business_id=business.id,
                    name=name,
                    description=fake.sentence(nb_words=12),
                    category=category,
                    price=price,
                    currency="INR",
                    stock_qty=random.choice([0, 0, 3, 5, 8, 12, 25, 40, 60]),
                    image_url=None,
                    is_active=True,
                    embedding=None,  # left NULL on purpose — see module docstring
                    created_at=now - timedelta(days=random.randint(30, DAYS_BACK)),
                )
                products.append(product)
                objects.append(product)

            # --- 4. FAQs ---------------------------------------------------
            faqs: list[Faq] = []
            faq_source = FAQ_SEED[:NUM_FAQS] if NUM_FAQS <= len(FAQ_SEED) else FAQ_SEED
            for question, answer, category in faq_source:
                faq = Faq(
                    id=uuid.uuid4(),
                    business_id=business.id,
                    question=question,
                    answer=answer,
                    category=category,
                    embedding=None,  # left NULL on purpose — see module docstring
                    created_at=now - timedelta(days=random.randint(30, DAYS_BACK)),
                )
                faqs.append(faq)
                objects.append(faq)

            # --- 5. Customers ------------------------------------------------
            customers: list[Customer] = []
            customer_channel: dict[uuid.UUID, ChannelType] = {}
            for _ in range(NUM_CUSTOMERS):
                channel = random.choice(CHANNELS)
                customer = Customer(
                    id=uuid.uuid4(),
                    business_id=business.id,
                    name=fake.name(),
                    phone=fake.phone_number() if channel == ChannelType.whatsapp else None,
                    instagram_handle=fake.user_name() if channel == ChannelType.instagram else None,
                    facebook_psid=str(uuid.uuid4()) if channel == ChannelType.facebook else None,
                    email=fake.email() if random.random() < 0.4 else None,
                    created_at=now - timedelta(days=random.randint(0, DAYS_BACK)),
                )
                customers.append(customer)
                customer_channel[customer.id] = channel
                objects.append(customer)

            # --- 6. Conversations + Messages ---------------------------------
            conversations: list[Conversation] = []
            conversation_channel: dict[uuid.UUID, ChannelType] = {}
            conversation_customer: dict[uuid.UUID, uuid.UUID] = {}

            status_weights = [
                (ConversationStatus.closed, 0.55),
                (ConversationStatus.open, 0.30),
                (ConversationStatus.handed_over, 0.15),
            ]
            statuses = [s for s, _ in status_weights]
            weights = [w for _, w in status_weights]

            for _ in range(NUM_CONVERSATIONS):
                customer = random.choice(customers)
                channel = customer_channel[customer.id]
                day_offset = weighted_day_offset()
                started_at = random_timestamp_on_day(day_offset)
                status = random.choices(statuses, weights=weights, k=1)[0]

                conversation = Conversation(
                    id=uuid.uuid4(),
                    business_id=business.id,
                    customer_id=customer.id,
                    channel=channel,
                    status=status,
                    assigned_staff_id=owner.id if status == ConversationStatus.handed_over else None,
                    started_at=started_at,
                    last_message_at=started_at,
                )
                conversations.append(conversation)
                conversation_channel[conversation.id] = channel
                conversation_customer[conversation.id] = customer.id
                objects.append(conversation)

                date_str = started_at.date().isoformat()
                bucket = kpi_bucket(date_str, channel)
                bucket["enquiries_count"] += 1
                if status != ConversationStatus.handed_over:
                    bucket["ai_resolved_count"] += 1

                # Build a short message thread.
                num_turns = random.randint(2, 5)  # customer/bot pairs
                current_time = started_at
                last_message_time = started_at
                for turn in range(num_turns):
                    # Customer message
                    customer_msg_time = current_time + timedelta(minutes=random.randint(0, 20))
                    customer_content = fake.sentence(nb_words=random.randint(6, 16))
                    customer_message = Message(
                        id=uuid.uuid4(),
                        conversation_id=conversation.id,
                        sender=SenderType.customer,
                        content=customer_content,
                        tool_calls=None,
                        tool_results=None,
                        external_message_id=f"ext-{uuid.uuid4()}",
                        created_at=customer_msg_time,
                    )
                    objects.append(customer_message)

                    # Bot message (occasionally with a tool call attached)
                    response_gap_seconds = random.randint(10, 150)
                    bot_msg_time = customer_msg_time + timedelta(seconds=response_gap_seconds)
                    sample = random.choice(TOOL_SAMPLES) if random.random() < 0.4 else None
                    bot_message = Message(
                        id=uuid.uuid4(),
                        conversation_id=conversation.id,
                        sender=SenderType.bot,
                        content=fake.sentence(nb_words=random.randint(8, 20)),
                        tool_calls=sample["tool_calls"] if sample else None,
                        tool_results=sample["tool_results"] if sample else None,
                        external_message_id=None,
                        created_at=bot_msg_time,
                    )
                    objects.append(bot_message)

                    bucket["response_seconds"].append(response_gap_seconds)
                    last_message_time = bot_msg_time
                    current_time = bot_msg_time

                # Staff message if handed over
                if status == ConversationStatus.handed_over:
                    staff_msg_time = last_message_time + timedelta(minutes=random.randint(1, 30))
                    staff_message = Message(
                        id=uuid.uuid4(),
                        conversation_id=conversation.id,
                        sender=SenderType.staff,
                        content=fake.sentence(nb_words=12),
                        tool_calls=None,
                        tool_results=None,
                        external_message_id=None,
                        created_at=staff_msg_time,
                    )
                    objects.append(staff_message)
                    last_message_time = staff_msg_time

                conversation.last_message_at = last_message_time

            # --- 7. Leads ------------------------------------------------------
            lead_status_weights = [
                (LeadStatus.new, 0.25),
                (LeadStatus.qualified, 0.25),
                (LeadStatus.hot, 0.20),
                (LeadStatus.lost, 0.15),
                (LeadStatus.converted, 0.15),
            ]
            lead_statuses = [s for s, _ in lead_status_weights]
            lead_weights = [w for _, w in lead_status_weights]

            leads: list[Lead] = []
            eligible_conversations = random.sample(
                conversations, k=max(1, int(len(conversations) * 0.55))
            )
            for conversation in eligible_conversations:
                status = random.choices(lead_statuses, weights=lead_weights, k=1)[0]
                lead = Lead(
                    id=uuid.uuid4(),
                    conversation_id=conversation.id,
                    customer_id=conversation_customer[conversation.id],
                    status=status,
                    score=random.randint(10, 95),
                    product_interest_id=random.choice(products).id if random.random() < 0.7 else None,
                    notes=fake.sentence(nb_words=10) if random.random() < 0.5 else None,
                    created_at=conversation.started_at,
                    updated_at=conversation.last_message_at,
                )
                leads.append(lead)
                objects.append(lead)

            # --- 8. Orders + Order Items ---------------------------------------
            order_status_weights = [
                (OrderStatus.confirmed, 0.35),
                (OrderStatus.fulfilled, 0.35),
                (OrderStatus.pending, 0.20),
                (OrderStatus.cancelled, 0.10),
            ]
            order_statuses = [s for s, _ in order_status_weights]
            order_weights = [w for _, w in order_status_weights]

            for lead in leads:
                should_order = lead.status == LeadStatus.converted or (
                    lead.status == LeadStatus.hot and random.random() < 0.3
                )
                if not should_order:
                    continue

                conversation = next(c for c in conversations if c.id == lead.conversation_id)
                order_created_at = min(
                    conversation.last_message_at + timedelta(hours=random.randint(1, 12)), now
                )
                num_items = random.randint(1, 3)
                chosen_products = random.sample(products, k=min(num_items, len(products)))

                order_items = []
                total = 0.0
                order_id = uuid.uuid4()
                for product in chosen_products:
                    quantity = random.randint(1, 3)
                    unit_price = float(product.price)
                    total += quantity * unit_price
                    order_items.append(
                        OrderItem(
                            id=uuid.uuid4(),
                            order_id=order_id,
                            product_id=product.id,
                            quantity=quantity,
                            unit_price=unit_price,
                        )
                    )

                status = random.choices(order_statuses, weights=order_weights, k=1)[0]
                order = Order(
                    id=order_id,
                    lead_id=lead.id,
                    customer_id=lead.customer_id,
                    status=status,
                    payment_method="cod",
                    address=fake.address().replace("\n", ", "),
                    total_amount=round(total, 2),
                    created_at=order_created_at,
                    updated_at=order_created_at,
                )
                objects.append(order)
                objects.extend(order_items)

                if status != OrderStatus.cancelled:
                    channel = conversation_channel[conversation.id]
                    date_str = order_created_at.date().isoformat()
                    bucket = kpi_bucket(date_str, channel)
                    bucket["orders_count"] += 1
                    bucket["revenue"] += round(total, 2)

            # --- 9. KPI daily snapshots -----------------------------------------
            for (date_str, channel), agg in kpi.items():
                response_seconds = agg["response_seconds"]
                avg_response = (
                    round(sum(response_seconds) / len(response_seconds), 2)
                    if response_seconds
                    else None
                )
                snapshot = KpiDailySnapshot(
                    id=uuid.uuid4(),
                    business_id=business.id,
                    date=date_str,
                    channel=channel,
                    enquiries_count=agg["enquiries_count"],
                    ai_resolved_count=agg["ai_resolved_count"],
                    avg_response_seconds=avg_response,
                    orders_count=agg["orders_count"],
                    revenue=round(agg["revenue"], 2),
                )
                objects.append(snapshot)

            # --- Commit everything in one transaction ---------------------------
            db.add_all(objects)
            await db.commit()

        except Exception:
            await db.rollback()
            raise

    print("Seed complete.")
    print(f"  BUSINESS_ID={business.id}")
    print(f"  Owner login: {OWNER_EMAIL} / {OWNER_PASSWORD}  (rotate after first login)")
    print(f"  Products: {len(products)}  Faqs: {len(faqs)}  Customers: {len(customers)}")
    print(f"  Conversations: {len(conversations)}  Leads: {len(leads)}")


if __name__ == "__main__":
    asyncio.run(seed())