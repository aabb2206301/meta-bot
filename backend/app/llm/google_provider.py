"""
Google (Gemini) implementation of LLMProvider (alternate chat provider).

>>> PHASE 1 TARGET — implement per PROJECT_PLAN.md section 3 <<<

Reference shape (from the plan):

    class GoogleProvider(LLMProvider):
        def __init__(self, api_key: str, model: str):
            self.client = genai.Client(api_key=api_key)
            self.model = model

        async def chat(self, messages, tools):
            gemini_tools = _convert_openai_tools_to_gemini(tools)
            contents = _convert_messages_to_gemini(messages)
            resp = await self.client.aio.models.generate_content(
                model=self.model, contents=contents,
                config=types.GenerateContentConfig(tools=gemini_tools),
            )
            # extract text / function_call parts into LLMResponse

The two `_convert_*` adapters are the ONLY place that should know Gemini's
wire format differs from OpenAI's. Keep them private to this module.

TODO:
- Implement _convert_openai_tools_to_gemini(tools: list[dict]) -> list
  (Gemini FunctionDeclaration format — role/parts structure differs from
  OpenAI's messages array; system messages need special handling since
  Gemini takes a separate system_instruction rather than a "system" role
  message in `contents`).
- Implement _convert_messages_to_gemini(messages: list[dict]) -> list
- Implement __init__ and chat(), extracting text + function_call parts
  from resp.candidates[0].content.parts into LLMResponse/ToolCall.
- Populate input_tokens/output_tokens from resp.usage_metadata.
"""
from .base import LLMProvider, LLMResponse, ToolCall  # noqa: F401


class GoogleProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        raise NotImplementedError("Phase 1: implement GoogleProvider")

    async def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        raise NotImplementedError("Phase 1: implement GoogleProvider.chat")
