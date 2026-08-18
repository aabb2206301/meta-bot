"""
get_llm_provider() — reads LLM_PROVIDER from settings and returns a working
LLMProvider. This is the only place in the codebase that decides which SDK
to instantiate; adding a third provider later means one new file + one new
line in _PROVIDERS, nothing else changes.

Design note (see resilient.py docstring): fallback wrapping happens HERE,
not in the caller. If LLM_FALLBACK_ENABLED=true and both provider keys are
present, get_llm_provider() returns a ResilientLLM transparently — the
orchestrator (Phase 4) just calls .chat() and never needs to know fallback
exists.
"""
from ..config import settings
from .base import LLMProvider
from .google_provider import GoogleProvider
from .groq_provider import GroqProvider
from .resilient import ResilientLLM

_PROVIDERS = {"groq": GroqProvider, "google": GoogleProvider}


def _build_provider(name: str) -> LLMProvider:
    """Build a named provider, raising a clear error if its required key is
    missing. Used for the primary provider, where missing config should be
    a loud startup failure, not a silent None."""
    if name == "groq":
        if not settings.groq_api_key:
            raise ValueError("LLM_PROVIDER=groq but GROQ_API_KEY is not set.")
        return GroqProvider(settings.groq_api_key, settings.groq_model)

    if name == "google":
        if not settings.google_api_key:
            raise ValueError("LLM_PROVIDER=google but GOOGLE_API_KEY is not set.")
        return GoogleProvider(settings.google_api_key, settings.google_model)

    raise ValueError(f"Unknown LLM_PROVIDER '{name}'. Use 'groq' or 'google'.")


def _build_optional_fallback_provider(name: str) -> LLMProvider | None:
    """Build the *other* provider for use as a fallback. Unlike
    _build_provider, missing config here is not an error — fallback is only
    ever a bonus, so we just skip it and let the caller run without one."""
    try:
        if name == "groq" and settings.groq_api_key:
            return GroqProvider(settings.groq_api_key, settings.groq_model)
        if name == "google" and settings.google_api_key:
            return GoogleProvider(settings.google_api_key, settings.google_model)
    except Exception:  # noqa: BLE001 - fallback construction must never
        # block startup; if it can't be built, we simply run without one.
        return None
    return None


def get_llm_provider() -> LLMProvider:
    primary_name = settings.llm_provider.lower()
    if primary_name not in _PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER '{primary_name}'. Use 'groq' or 'google'.")

    primary = _build_provider(primary_name)

    if not settings.llm_fallback_enabled:
        return primary

    secondary_name = "google" if primary_name == "groq" else "groq"
    secondary = _build_optional_fallback_provider(secondary_name)

    if secondary is None:
        # Fallback wanted but not configured (e.g. GOOGLE_API_KEY unset while
        # LLM_PROVIDER=groq) — proceed on the primary alone rather than fail.
        return primary

    return ResilientLLM(primary=primary, secondary=secondary)