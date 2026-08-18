"""
Groq implementation of LLMProvider (default chat provider).

Groq's chat.completions API is OpenAI-compatible, so the tool schema in
tools/registry.py (written once, in OpenAI's function-calling format) is
passed straight through with no translation — unlike GoogleProvider,
which needs adapter functions.
"""
import json
import logging

from groq import AsyncGroq

from .base import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.client = AsyncGroq(api_key=api_key)
        self.model = model

    async def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        # Groq's API rejects an empty tools array in some SDK/model combos —
        # only pass tools/tool_choice when there's actually something to offer.
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        completion = await self.client.chat.completions.create(**kwargs)
        choice = completion.choices[0].message

        tool_calls: list[ToolCall] = []
        for tc in (choice.tool_calls or []):
            try:
                arguments = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                # The model occasionally emits malformed JSON. Don't crash the
                # whole turn over it — surface the raw string so the caller
                # (or a future retry) can decide what to do with it.
                logger.warning(
                    "Groq returned non-JSON tool arguments for %s: %r",
                    tc.function.name,
                    tc.function.arguments,
                )
                arguments = {"_raw_arguments": tc.function.arguments}
            tool_calls.append(
                ToolCall(id=tc.id, name=tc.function.name, arguments=arguments)
            )

        usage = completion.usage
        return LLMResponse(
            text=choice.content,
            tool_calls=tool_calls,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )