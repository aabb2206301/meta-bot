"""
get_embedding_provider() — reads settings.embedding_provider. If Google
isn't configured (no GOOGLE_API_KEY), callers should fall back to plain
Postgres keyword search (ILIKE / full-text) rather than crash — that
fallback decision lives in the tool that calls this (product_tools.py /
faq_tools.py, Phase 3), not here.

>>> PHASE 2 TARGET — implement per PROJECT_PLAN.md section 3 <<<

TODO:
- def get_embedding_provider() -> EmbeddingProvider | None:
      return None if no provider is configured (empty API key), so
      calling code can branch to keyword search instead of raising.
- Keep this file provider-agnostic even though only Google is implemented
  today — mirror llm/factory.py's _PROVIDERS dict pattern so adding
  OpenAI embeddings later is a one-line change.
"""
from .base import EmbeddingProvider


def get_embedding_provider() -> EmbeddingProvider | None:
    raise NotImplementedError("Phase 2: implement get_embedding_provider()")
