"""
Faker-based historical data generator — populates a business with
plausible customers, conversations, messages, leads, orders, products,
FAQs, and backfills kpi_daily_snapshot so the dashboard has something to
show on day one instead of an empty state.

>>> PHASE 7 TARGET — implement per PROJECT_PLAN.md section 2 & 5 <<<

TODO:
- Runnable as `python -m app.seed.seed_data` (add an `if __name__ ==
  "__main__":` block using asyncio.run).
- Create one Business row (print its id — the user needs to copy this
  into .env as BUSINESS_ID).
- Create ~10-20 Products with realistic names/prices/stock for whatever
  product category you choose (keep it generic/configurable rather than
  hardcoding a specific niche).
- Create ~5-10 Faqs (shipping, returns, payment).
- Create ~30-50 Customers across the three channels.
- Create Conversations + Messages with realistic timestamps spread over
  the last ~60 days, weighted so recent days have more activity — this
  is what makes the dashboard's trend charts look real instead of flat.
- Create a mix of Leads at different statuses and Orders at different
  statuses tied to some of those conversations.
- Compute and insert KpiDailySnapshot rows by aggregating the generated
  data per day per channel (enquiries_count, ai_resolved_count,
  avg_response_seconds, orders_count, revenue) — don't hand-wave these,
  the dashboard reads this table directly rather than aggregating raw
  messages on every page load.
- Skip embeddings during seeding (leave embedding columns NULL) unless
  you want to also burn API quota seeding — call out this tradeoff in a
  comment; product/faq search will fall back to keyword search for
  seeded rows until someone runs a separate backfill script.
- Wrap the whole thing in one DB transaction per business so a failed
  seed run doesn't leave partial data.
"""


async def seed() -> None:
    raise NotImplementedError("Phase 7: implement seed()")
