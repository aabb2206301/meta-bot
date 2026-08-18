"""
REST endpoints the React dashboard reads from: KPIs, conversations,
orders, products (and staff auth).

>>> PHASE 6 TARGET — implement per PROJECT_PLAN.md sections 1-2 & 5 <<<

TODO (suggested route list — adjust as the frontend pages in Phase 9-10
actually need):
- POST /api/auth/login            — email+password against staff_users,
    return a JWT (settings.jwt_secret / jwt_expire_minutes).
- GET  /api/kpis/summary          — reads kpi_daily_snapshot, aggregated
    for whatever date range the dashboard requests (query params:
    from, to, channel). This is what powers Dashboard.tsx (Phase 9).
- GET  /api/conversations         — paginated list, filterable by status
    and channel; include customer name + last_message_at + channel.
- GET  /api/conversations/{id}/messages — full message history for one
    conversation (powers Conversations.tsx, Phase 9).
- GET  /api/orders                — paginated, filterable by status.
- PATCH /api/orders/{id}          — staff manually updates order status
    (separate from the LLM's update_order_status tool — this is the
    human path, reuse the same DB write logic if practical).
- GET  /api/products              — paginated, filterable by category.
- POST /api/products, PATCH /api/products/{id} — staff CRUD on catalog.
    Remember: if you change price/stock/description on a product with an
    existing `embedding`, the embedding is now stale — either
    re-embed on save (calls embeddings/factory.py) or accept staleness
    for now and note it as a known limitation.
- All routes except /api/auth/login should require a valid JWT (FastAPI
  dependency, decode + verify settings.jwt_secret) and scope every query
  by the business_id encoded in that JWT — this is the same
  trusted-identity boundary tools/order_tools.py applies to the bot,
  applied here to staff.
- Register this router in main.py (Phase 6 also touches main.py).
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["dashboard"])
