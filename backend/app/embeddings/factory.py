"""
get_embedding_provider() — reads EMBEDDING_PROVIDER from settings.

Unlike llm/factory.py, missing configuration here is NOT an error: product/
FAQ semantic search is a nice-to-have, not a hard dependency of the bot.
Callers (tools/product_tools.py::search_products, tools/faq_tools.py::
search_faqs, Phase 3) must check for None and fall back to a plain Postgres
ILIKE / full-text keyword query instead of crashing the conversation.
"""
import logging

from ..config import settings
from .base import EmbeddingProvider
from .google_embeddings import GoogleEmbeddingProvider

logger = logging.getLogger(__name__)

_PROVIDERS = {"google": GoogleEmbeddingProvider}


def get_embedding_provider() -> EmbeddingProvider | None:
    name = settings.embedding_provider.lower()

    if name not in _PROVIDERS:
        logger.warning(
            "Unknown EMBEDDING_PROVIDER '%s' — falling back to keyword search.", name
        )
        return None

    if name == "google":
        if not settings.google_api_key:
            logger.warning(
                "EMBEDDING_PROVIDER=google but GOOGLE_API_KEY is not set — "
                "falling back to keyword search."
            )
            return None
        return GoogleEmbeddingProvider(
            api_key=settings.google_api_key,
            model=settings.embedding_model,
            output_dimensionality=settings.embedding_dimensions,
        )

    return None