"""
ResilientLLM — wraps a primary LLMProvider with a bounded retry, then falls
back to a secondary provider if one is configured. This is what makes the
"default + alternate" provider setup actually useful at runtime (e.g. Groq
rate-limits mid-conversation), not just a config toggle you flip by hand.

Design note: wrapping is done inside llm/factory.py, not by callers. Callers
(the orchestrator, Phase 4) always just get something satisfying
LLMProvider — they never need to know whether fallback is active.
"""
import asyncio
import logging

from .base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class ResilientLLM(LLMProvider):
    def __init__(
        self,
        primary: LLMProvider,
        secondary: LLMProvider | None = None,
        max_retries: int = 1,
        retry_backoff_seconds: float = 1.0,
    ):
        self.primary = primary
        self.secondary = secondary
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    async def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        last_exc: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return await self.primary.chat(messages, tools)
            except Exception as exc:  # noqa: BLE001 - deliberately broad: any
                # failure from either SDK (rate limit, timeout, 5xx, transport
                # error) should trigger retry/fallback rather than killing the
                # conversation. Non-retryable programmer errors (e.g. a bad
                # tool schema) will also hit this, fail the same way on
                # retry/fallback, and surface via the final raise below.
                last_exc = exc
                logger.warning(
                    "Primary LLM provider (%s) failed on attempt %d/%d: %s",
                    type(self.primary).__name__,
                    attempt + 1,
                    self.max_retries + 1,
                    exc,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_backoff_seconds * (attempt + 1))

        if self.secondary is not None:
            logger.error(
                "Primary LLM provider (%s) exhausted retries, falling back to %s",
                type(self.primary).__name__,
                type(self.secondary).__name__,
            )
            try:
                return await self.secondary.chat(messages, tools)
            except Exception as fallback_exc:  # noqa: BLE001
                logger.error(
                    "Fallback LLM provider (%s) also failed: %s",
                    type(self.secondary).__name__,
                    fallback_exc,
                )
                raise RuntimeError(
                    "Both primary and fallback LLM providers failed"
                ) from fallback_exc

        assert last_exc is not None
        raise last_exc