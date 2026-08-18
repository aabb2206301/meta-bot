"""
EmbeddingProvider abstract interface. Complete in the boilerplate — mirrors
the shape of llm/base.py, kept intentionally minimal.
"""
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return a single embedding vector for `text`."""
        raise NotImplementedError

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input string, same order."""
        raise NotImplementedError
