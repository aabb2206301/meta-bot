"""
Google (Gemini) implementation of LLMProvider (alternate chat provider).

Gemini's wire format differs from OpenAI's in three ways that matter here:
  1. Tool schemas use google.genai.types.Schema (Type enum, not lowercase
     JSON-schema strings) instead of raw JSON Schema.
  2. There's no flat message list — turns are `Content(role=..., parts=[...])`,
     roles are only "user" / "model" / "function", and a system prompt is a
     separate `system_instruction` config field, not a message in the list.
  3. Tool calls/results are typed `Part.function_call` / `Part.function_response`
     objects, not `{"tool_calls": [...]}` dict keys, and Gemini doesn't return
     a call id — we mint one so results can still be paired up by the caller.

The two `_convert_*` functions below are the only place any of that leaks.
Everything else in the codebase only ever sees the shared LLMResponse shape.
"""
import logging
import uuid

from google import genai
from google.genai import types

from .base import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)

# JSON-schema "type" (as used in tools/registry.py, OpenAI-style, lowercase)
# -> Gemini's types.Type enum.
_JSON_TYPE_TO_GEMINI = {
    "string": types.Type.STRING,
    "number": types.Type.NUMBER,
    "integer": types.Type.INTEGER,
    "boolean": types.Type.BOOLEAN,
    "array": types.Type.ARRAY,
    "object": types.Type.OBJECT,
}


def _json_schema_to_gemini_schema(schema: dict) -> types.Schema:
    """Recursively convert one JSON-schema node (as used in the OpenAI-format
    tool definitions in tools/registry.py) into a types.Schema node."""
    gemini_type = _JSON_TYPE_TO_GEMINI.get(schema.get("type", "string"), types.Type.STRING)

    kwargs: dict = {"type": gemini_type}
    if "description" in schema:
        kwargs["description"] = schema["description"]
    if "enum" in schema:
        kwargs["enum"] = schema["enum"]

    if gemini_type == types.Type.OBJECT and "properties" in schema:
        kwargs["properties"] = {
            key: _json_schema_to_gemini_schema(value)
            for key, value in schema["properties"].items()
        }
        if "required" in schema:
            kwargs["required"] = schema["required"]

    if gemini_type == types.Type.ARRAY and "items" in schema:
        kwargs["items"] = _json_schema_to_gemini_schema(schema["items"])

    return types.Schema(**kwargs)


def _convert_openai_tools_to_gemini(tools: list[dict]) -> list[types.Tool] | None:
    if not tools:
        return None
    declarations = []
    for entry in tools:
        fn = entry["function"]
        declarations.append(
            types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=_json_schema_to_gemini_schema(
                    fn.get("parameters", {"type": "object", "properties": {}})
                ),
            )
        )
    return [types.Tool(function_declarations=declarations)]


def _convert_messages_to_gemini(
    messages: list[dict],
) -> tuple[str | None, list[types.Content]]:
    """Returns (system_instruction, contents). System-role messages are
    pulled out of the list and joined into one instruction string, since
    Gemini has no "system" turn in `contents`."""
    system_parts: list[str] = []
    contents: list[types.Content] = []

    for msg in messages:
        role = msg.get("role")

        if role == "system":
            if msg.get("content"):
                system_parts.append(msg["content"])
            continue

        if role == "user":
            contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=msg.get("content") or "")])
            )
            continue

        if role == "assistant":
            parts = []
            if msg.get("content"):
                parts.append(types.Part.from_text(text=msg["content"]))
            for tc in msg.get("tool_calls") or []:
                fn = tc["function"]
                import json as _json

                try:
                    args = _json.loads(fn["arguments"])
                except (ValueError, TypeError):
                    args = {}
                parts.append(
                    types.Part(function_call=types.FunctionCall(name=fn["name"], args=args))
                )
            if parts:
                contents.append(types.Content(role="model", parts=parts))
            continue

        if role == "tool":
            contents.append(
                types.Content(
                    role="function",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=msg.get("name", ""),
                                response={"result": msg.get("content", "")},
                            )
                        )
                    ],
                )
            )
            continue

        logger.warning("Skipping message with unrecognized role for Gemini: %r", role)

    return ("\n".join(system_parts) if system_parts else None), contents


class GoogleProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        system_instruction, contents = _convert_messages_to_gemini(messages)
        gemini_tools = _convert_openai_tools_to_gemini(tools)

        config = types.GenerateContentConfig(
            tools=gemini_tools,
            system_instruction=system_instruction,
            # We dispatch tool calls ourselves (tools/registry.py + the
            # orchestrator's trust boundary) — never let the SDK auto-invoke
            # anything on our behalf.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        candidate = response.candidates[0] if response.candidates else None
        parts = candidate.content.parts if candidate and candidate.content else []
        for part in parts:
            if getattr(part, "text", None):
                text_parts.append(part.text)
            fc = getattr(part, "function_call", None)
            if fc is not None:
                # Gemini doesn't hand back a call id the way OpenAI/Groq do —
                # mint one so the orchestrator can still pair this call with
                # the tool result message it appends afterward.
                tool_calls.append(
                    ToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=fc.name, arguments=dict(fc.args or {}))
                )

        usage = getattr(response, "usage_metadata", None)
        return LLMResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        )