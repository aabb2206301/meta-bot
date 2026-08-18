"""
get_llm_provider() — reads settings.llm_provider and returns the right
adapter. Adding a third provider later means one new file + one new line
in _PROVIDERS; nothing else changes.

>>> PHASE 1 TARGET — implement per PROJECT_PLAN.md section 3 <<<

TODO:
- Import GroqProvider / GoogleProvider once they exist (Phase 1 also
  implements those two files — do all three together).
- Raise a clear ValueError if the required API key for the selected
  provider is missing, per the plan's factory() reference code.
- Optionally wrap the returned provider in ResilientLLM (resilient.py)
  here if settings.llm_fallback_enabled and a secondary key is present —
  or leave that composition to bot/orchestrator.py (Phase 4). Pick one
  and be consistent; document the choice in this file's docstring once done.
"""
from .base import LLMProvider


def get_llm_provider() -> LLMProvider:
    raise NotImplementedError("Phase 1: implement get_llm_provider()")
