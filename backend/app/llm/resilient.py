"""
ResilientLLM — wraps a primary LLMProvider; on failure (rate limit,
timeout, 5xx) retries once, then falls back to a secondary provider if
configured and settings.llm_fallback_enabled is true.

>>> PHASE 1 TARGET — implement per PROJECT_PLAN.md section 3 <<<

TODO:
- class ResilientLLM(LLMProvider):
      def __init__(self, primary: LLMProvider, secondary: LLMProvider | None): ...
      async def chat(self, messages, tools) -> LLMResponse:
          try: retry primary once on known transient errors
          except <transient error>: fall back to secondary if present
- Define/import a shared "transient LLM error" concept so this file
  doesn't need to know each provider's SDK-specific exception classes —
  either normalize exceptions in groq_provider.py/google_provider.py, or
  catch broadly here and log what actually failed.
- Log every fallback event (at minimum: which provider failed, why, and
  which provider served the request) — useful during a live demo when
  Groq rate-limits mid-conversation.
"""
from .base import LLMProvider, LLMResponse


class ResilientLLM(LLMProvider):
    def __init__(self, primary: LLMProvider, secondary: LLMProvider | None = None):
        raise NotImplementedError("Phase 1: implement ResilientLLM")

    async def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        raise NotImplementedError("Phase 1: implement ResilientLLM.chat")
