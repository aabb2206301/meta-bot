"""
Google implementation of EmbeddingProvider, using text-embedding-004 (or
whatever settings.embedding_model is set to).

>>> PHASE 2 TARGET — implement per PROJECT_PLAN.md section 3 <<<

TODO:
- class GoogleEmbeddings(EmbeddingProvider):
      def __init__(self, api_key: str, model: str): self.client = genai.Client(api_key=api_key); ...
      async def embed(self, text: str) -> list[float]:
          call self.client.aio.models.embed_content(model=self.model, contents=text)
          return the .values list from the response
      async def embed_batch(self, texts: list[str]) -> list[list[float]]:
          batch call if the SDK supports it, else loop + gather
- Confirm the output dimension matches settings.embedding_dimensions (768
  for text-embedding-004) — this MUST match the `Vector(768)` column
  width in db/models.py or inserts will fail.
- Raise a clear error if api_key is missing rather than letting the SDK
  fail with an opaque message.
"""
from .base import EmbeddingProvider


class GoogleEmbeddings(EmbeddingProvider):
    def __init__(self, api_key: str, model: str):
        raise NotImplementedError("Phase 2: implement GoogleEmbeddings")

    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError("Phase 2: implement GoogleEmbeddings.embed")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Phase 2: implement GoogleEmbeddings.embed_batch")
