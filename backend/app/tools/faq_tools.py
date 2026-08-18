"""
search_faqs — same pattern as search_products but against the `faqs`
table (see product_tools.py for the embedding-vs-keyword-search decision
this should mirror).

>>> PHASE 3 TARGET — implement per PROJECT_PLAN.md sections 3-4 <<<

TODO:
- async def search_faqs(db, *, business_id: str, args: dict) -> dict:
    - args["query"] from the LLM.
    - Same embed-then-vector-search-else-ILIKE pattern as
      product_tools.search_products — consider factoring the shared
      "embed or fall back to ILIKE" logic into a small helper both files
      import, rather than duplicating it.
    - Return top ~3 matches as {"question", "answer"} pairs.
"""


async def search_faqs(db, *, business_id: str, args: dict) -> dict:
    raise NotImplementedError("Phase 3: implement search_faqs")
