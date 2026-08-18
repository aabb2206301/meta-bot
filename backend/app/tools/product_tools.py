"""
search_products, check_stock — the only two tools that touch the
`products` table. The LLM never queries the DB directly; these functions
are the trusted boundary (see PROJECT_PLAN.md section 4).

>>> PHASE 3 TARGET — implement per PROJECT_PLAN.md sections 3-4 <<<

TODO:
- async def search_products(db, *, business_id: str, args: dict) -> dict:
    - args["query"] comes from the LLM.
    - Try embeddings/factory.get_embedding_provider() first: if it
      returns a provider, embed the query and do a pgvector cosine
      distance search (`ORDER BY embedding <=> :query_embedding LIMIT 5`)
      scoped to `business_id` and `is_active = true`.
    - If get_embedding_provider() returns None, fall back to
      `ILIKE '%query%'` across name/description/category.
    - Return a small serializable dict/list (id, name, price, stock_qty,
      currency) — NOT full SQLAlchemy model objects, since this result
      gets appended to the message list and sent back to the LLM as text.

- async def check_stock(db, *, business_id: str, args: dict) -> dict:
    - args["product_id"] comes from the LLM.
    - Look up the product scoped to business_id (never trust product_id
      alone without the business_id filter — see the create_order
      trust-boundary note in order_tools.py for why this matters).
    - Return {"product_id", "stock_qty", "is_active"}.

Signature note: `business_id` is injected by the orchestrator from the
webhook's trusted context, exactly like `conversation_id` in
order_tools.create_order — never accept it as an LLM argument.
"""


async def search_products(db, *, business_id: str, args: dict) -> dict:
    raise NotImplementedError("Phase 3: implement search_products")


async def check_stock(db, *, business_id: str, args: dict) -> dict:
    raise NotImplementedError("Phase 3: implement check_stock")
