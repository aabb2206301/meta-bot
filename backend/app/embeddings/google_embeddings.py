"""
Google implementation of EmbeddingProvider, used for product/FAQ semantic
search. Groq has no embeddings endpoint, so this is the only embeddings
provider today — see embeddings/factory.py for what happens when it isn't
configured (keyword-search fallback, not a crash).

IMPORTANT: the vector this returns must be exactly `settings.embedding_
dimensions` (768 by default) long, because that's the width baked into the
`Vector(768)` column on Product.embedding / Faq.embedding in db/models.py.
If you ever change EMBEDDING_MODEL or EMBEDDING_DIMENSIONS, both the env
var and the DB column width (via a new migration) need to change together
— this file alone can't make that safe.
"""
from google import genai
from google.genai import types

from .base import EmbeddingProvider


class GoogleEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str, output_dimensionality: int):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.output_dimensionality = output_dimensionality

    async def embed(self, text: str) -> list[float]:
        (vector,) = await self.embed_batch([text])
        return vector

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response = await self.client.aio.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=self.output_dimensionality),
        )

        vectors = [list(embedding.values) for embedding in response.embeddings]

        for vector in vectors:
            if len(vector) != self.output_dimensionality:
                # Fail loud rather than silently write a mismatched-width
                # vector into a pgvector column that expects a fixed size.
                raise ValueError(
                    f"Google embeddings returned dimension {len(vector)}, "
                    f"expected {self.output_dimensionality} "
                    "(settings.embedding_dimensions / Vector(768) column width). "
                    "If you changed EMBEDDING_MODEL, update EMBEDDING_DIMENSIONS "
                    "and the matching Alembic migration too."
                )

        return vectors