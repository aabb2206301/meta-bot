"""
Groq implementation of LLMProvider (default chat provider).

>>> PHASE 1 TARGET — implement per PROJECT_PLAN.md section 3 <<<

Reference shape (from the plan — verify against the current `groq` SDK
version pinned in requirements.txt, since tool-call response shapes do
shift between SDK versions):

    class GroqProvider(LLMProvider):
        def __init__(self, api_key: str, model: str):
            self.client = AsyncGroq(api_key=api_key)
            self.model = model

        async def chat(self, messages, tools):
            resp = await self.client.chat.completions.create(
                model=self.model, messages=messages, tools=tools, tool_choice="auto",
            )
            choice = resp.choices[0].message
            tool_calls = [
                ToolCall(id=tc.id, name=tc.function.name,
                         arguments=json.loads(tc.function.arguments))
                for tc in (choice.tool_calls or [])
            ]
            return LLMResponse(
                text=choice.content, tool_calls=tool_calls,
                input_tokens=resp.usage.prompt_tokens,
                output_tokens=resp.usage.completion_tokens,
            )

Groq's API is OpenAI-compatible, so tools/registry.py's schema (OpenAI
format) passes straight through with no conversion.

TODO:
- Implement __init__ and chat() as above.
- Wrap the API call in try/except for groq.APIError / RateLimitError /
  APITimeoutError and re-raise as a common exception type that
  llm/resilient.py knows how to catch (define it there or here).
- Handle the case where choice.content is None but tool_calls is also
  empty (shouldn't happen, but don't let it crash silently).
"""
from .base import LLMProvider, LLMResponse, ToolCall  # noqa: F401


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        raise NotImplementedError("Phase 1: implement GroqProvider")

    async def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        raise NotImplementedError("Phase 1: implement GroqProvider.chat")
