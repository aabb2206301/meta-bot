"""
LLMProvider abstract interface — shared shape every provider adapter must
return, so the orchestrator never needs to know which LLM it's talking to.
Complete in the boilerplate, taken directly from PROJECT_PLAN.md section 3.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        """
        messages: OpenAI-style [{role, content}, ...].
        tools: OpenAI-style function-calling schema (see tools/registry.py).
        Each provider adapter is responsible for translating both into its
        own wire format internally — callers never need to know the
        difference.
        """
        raise NotImplementedError
