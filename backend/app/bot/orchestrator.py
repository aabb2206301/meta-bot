"""
The conversation loop — ties together llm/factory.py, tools/registry.py +
tools/*.py, and db/models.py.

=== Design decisions made in this phase (not fully pinned down by the
    stub/plan) — documented here so later phases don't have to guess ===

1. LLM provider lifecycle: get_llm_provider() builds real SDK clients
   (HTTP connection pools etc.), so it's built ONCE, lazily, on first use,
   and reused for the lifetime of the process — not re-built per call.
   See `_get_llm_provider()` below.

2. llm_call_log provider/model fields: LLMResponse (llm/base.py) does not
   report which underlying provider actually served a call, so when
   LLM_FALLBACK_ENABLED=true and ResilientLLM silently falls back from
   groq -> google mid-call, this log will still show the *configured*
   primary provider/model. This is a known gap — closing it properly
   means adding a `provider`/`model` field to LLMResponse (llm/base.py,
   Phase 1's file), which is out of scope here. Flagging it rather than
   silently logging something misleading.

3. Message-row reconstruction format: `messages.tool_calls` /
   `messages.tool_results` are stored as:
     tool_calls   = [{"id": ..., "name": ..., "arguments": {...}}, ...]
     tool_results = {tool_call_id: {...result dict...}, ...}
   One `messages` row (sender='bot') represents one full tool-call round
   (the assistant's tool_calls plus their results); a separate row
   (sender='bot', tool_calls=None) holds the final plain-text reply.
   `_load_history_messages` below expands stored rows back into the
   OpenAI-style {role, content, tool_calls / tool_call_id} sequence the
   LLMProvider.chat() interface expects.

4. Tool-call loop cap: if MAX_TOOL_ROUNDS is hit without the model
   producing plain text, the orchestrator does NOT just apologize — it
   calls request_human_handover itself (a stuck tool loop is exactly the
   "can't confidently continue" case the system prompt tells the model to
   hand off for) and returns a customer-facing message saying a team
   member will follow up.

5. sender='staff' rows are folded into the LLM's history as role
   "assistant" (a staff reply looks like "the business responded" from
   the customer's/model's point of view). If you want the model to be
   explicitly aware a human took over mid-conversation, revisit this.

6. (Phase 6) Dashboard live-push hook: after persisting the bot's final
   text reply, we call websocket.py's broadcast_new_message() so staff
   watching the dashboard see it without polling. This is the one
   explicitly-allowed cross-phase edit noted in IMPLEMENTATION_PLAN.md's
   Phase 6 section — a single call, nothing structural. It only fires for
   the final plain-text reply of a turn (not each tool-call round, and
   not as a dedicated "handover" event) — see websocket.py's docstring
   for that scope note.
"""
import importlib
import json
import logging
import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.websocket import broadcast_new_message
from ..config import settings
from ..db.models import Business, LlmCallLog, Message, SenderType
from ..llm.base import LLMProvider, LLMResponse, ToolCall
from ..llm.factory import get_llm_provider
from ..tools.registry import TOOL_DISPATCH_MAP, TOOLS
from .prompts import build_system_prompt

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5

# --- Tool dispatch -----------------------------------------------------

# TOOL_DISPATCH_MAP (tools/registry.py) gives us dotted string paths, not
# live references, so each is resolved once at import time via
# importlib rather than an if/elif chain per call.
def _resolve_tool(dotted_path: str):
    module_path, func_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


_TOOL_FUNCTIONS = {name: _resolve_tool(path) for name, path in TOOL_DISPATCH_MAP.items()}

# Each tool's signature differs slightly (see tools/*.py) — this maps
# each tool name to the trusted-context kwargs it needs, keyed off the
# ctx dict handle_incoming_message builds. `args` (LLM-supplied) is
# always passed separately by _execute_tool_call.
_TOOL_CONTEXT_KWARGS = {
    "search_products": lambda ctx: {"business_id": ctx["business_id"]},
    "check_stock": lambda ctx: {"business_id": ctx["business_id"]},
    "search_faqs": lambda ctx: {"business_id": ctx["business_id"]},
    "upsert_lead": lambda ctx: {
        "conversation_id": ctx["conversation_id"],
        "customer_id": ctx["customer_id"],
    },
    "create_order": lambda ctx: {"conversation_id": ctx["conversation_id"]},
    "update_order_status": lambda ctx: {"customer_id": ctx["customer_id"]},
    "request_human_handover": lambda ctx: {"conversation_id": ctx["conversation_id"]},
}


async def _execute_tool_call(db: AsyncSession, tool_call: ToolCall, ctx: dict) -> dict:
    func = _TOOL_FUNCTIONS.get(tool_call.name)
    if func is None:
        logger.error("Model called unknown tool '%s'", tool_call.name)
        return {"error": f"unknown tool '{tool_call.name}'"}

    kwargs_builder = _TOOL_CONTEXT_KWARGS.get(tool_call.name)
    context_kwargs = kwargs_builder(ctx) if kwargs_builder else {}

    try:
        return await func(db, args=tool_call.arguments, **context_kwargs)
    except Exception:  # noqa: BLE001 - a broken tool call must not kill the
        # conversation; surface it to the model as a tool error instead.
        logger.exception("Tool '%s' raised during execution", tool_call.name)
        await db.rollback()
        return {"error": f"internal error running '{tool_call.name}'"}


# --- LLM provider lifecycle ---------------------------------------------

_llm_provider: LLMProvider | None = None


def _get_llm_provider() -> LLMProvider:
    """Built once, lazily, and reused — see design note 1 above."""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = get_llm_provider()
    return _llm_provider


# --- Message persistence / history reconstruction ------------------------


async def _persist_customer_message(
    db: AsyncSession, *, conversation_id: str, text: str, external_message_id: str
) -> Message | None:
    """
    Insert the incoming customer message. Returns None (without raising)
    if this is a duplicate delivery per the UNIQUE(conversation_id,
    external_message_id) constraint — i.e. a Meta webhook retry — so the
    caller can no-op instead of re-running the LLM.
    """
    message = Message(
        conversation_id=conversation_id,
        sender=SenderType.customer,
        content=text,
        external_message_id=external_message_id,
    )
    db.add(message)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.info(
            "Duplicate webhook delivery for conversation=%s external_message_id=%s — skipping.",
            conversation_id,
            external_message_id,
        )
        return None
    await db.refresh(message)
    return message


async def _persist_bot_tool_round(
    db: AsyncSession,
    *,
    conversation_id: str,
    tool_calls: list[dict],
    tool_results: dict,
) -> None:
    message = Message(
        conversation_id=conversation_id,
        sender=SenderType.bot,
        content=None,
        tool_calls=tool_calls,
        tool_results=tool_results,
    )
    db.add(message)
    await db.commit()


async def _persist_bot_text_message(db: AsyncSession, *, conversation_id: str, text: str) -> None:
    message = Message(
        conversation_id=conversation_id,
        sender=SenderType.bot,
        content=text,
    )
    db.add(message)
    await db.commit()


def _row_to_llm_messages(row: Message) -> list[dict]:
    """Expand one stored `messages` row into the OpenAI-style dicts the
    LLMProvider.chat() interface expects — see design note 3 above."""
    if row.sender == SenderType.customer:
        return [{"role": "user", "content": row.content or ""}]

    if row.sender == SenderType.staff:
        return [{"role": "assistant", "content": row.content or ""}]

    # sender == bot
    out: list[dict] = []
    if row.tool_calls:
        out.append(
            {
                "role": "assistant",
                "content": row.content,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]),
                        },
                    }
                    for tc in row.tool_calls
                ],
            }
        )
        results = row.tool_results or {}
        for tc in row.tool_calls:
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(results.get(tc["id"], {})),
                }
            )
    elif row.content is not None:
        out.append({"role": "assistant", "content": row.content})

    return out


async def _load_history_messages(db: AsyncSession, conversation_id: str) -> list[dict]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(settings.max_history_messages)
    )
    result = await db.execute(stmt)
    rows = list(reversed(result.scalars().all()))  # oldest first

    messages: list[dict] = []
    for row in rows:
        messages.extend(_row_to_llm_messages(row))
    return messages


async def _log_llm_call(
    db: AsyncSession,
    *,
    conversation_id: str,
    response: LLMResponse,
    latency_ms: int,
) -> None:
    # See design note 2: provider/model reflect config, not necessarily
    # which one actually served this call if fallback occurred.
    provider_name = settings.llm_provider.lower()
    model_name = settings.groq_model if provider_name == "groq" else settings.google_model

    log_row = LlmCallLog(
        conversation_id=conversation_id,
        provider=provider_name,
        model=model_name,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        latency_ms=latency_ms,
    )
    db.add(log_row)
    await db.commit()


# --- Main entrypoint -----------------------------------------------------


async def handle_incoming_message(
    db: AsyncSession,
    *,
    conversation_id: str,
    customer_id: str,
    business_id: str,
    channel: str,
    text: str,
    external_message_id: str,
) -> str:
    """
    Runs the full load -> chat -> dispatch tools -> reply loop for one
    incoming customer message. Returns the final plain-text reply; the
    caller (a channel webhook handler, Phase 5) is responsible for
    actually sending it and for any channel-specific formatting/chunking.

    Returns "" if this turns out to be a duplicate webhook delivery
    (nothing new to send).
    """
    inserted = await _persist_customer_message(
        db,
        conversation_id=conversation_id,
        text=text,
        external_message_id=external_message_id,
    )
    if inserted is None:
        return ""

    business = await db.get(Business, business_id)
    business_name = business.name if business else "our store"

    system_prompt = build_system_prompt(business_name, channel=channel)
    history = await _load_history_messages(db, conversation_id)
    messages: list[dict] = [{"role": "system", "content": system_prompt}] + history

    provider = _get_llm_provider()
    ctx = {
        "business_id": business_id,
        "conversation_id": conversation_id,
        "customer_id": customer_id,
    }

    final_text: str | None = None

    for _round in range(MAX_TOOL_ROUNDS):
        start = time.perf_counter()
        response = await provider.chat(messages, TOOLS)
        latency_ms = int((time.perf_counter() - start) * 1000)

        await _log_llm_call(
            db, conversation_id=conversation_id, response=response, latency_ms=latency_ms
        )

        if not response.tool_calls:
            final_text = response.text or ""
            break

        # Keep the in-memory `messages` list in sync so the next chat()
        # call in this loop has the tool round in its context.
        messages.append(
            {
                "role": "assistant",
                "content": response.text,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in response.tool_calls
                ],
            }
        )

        tool_calls_payload = []
        tool_results_payload = {}
        for tc in response.tool_calls:
            result = await _execute_tool_call(db, tc, ctx)
            tool_calls_payload.append({"id": tc.id, "name": tc.name, "arguments": tc.arguments})
            tool_results_payload[tc.id] = result
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)}
            )

        await _persist_bot_tool_round(
            db,
            conversation_id=conversation_id,
            tool_calls=tool_calls_payload,
            tool_results=tool_results_payload,
        )
    else:
        # Cap reached without the model producing a plain-text reply —
        # see design note 4. Hand the conversation off ourselves rather
        # than leaving the customer with nothing.
        logger.warning(
            "Tool-call loop hit MAX_TOOL_ROUNDS=%d for conversation=%s without a final reply — forcing handover.",
            MAX_TOOL_ROUNDS,
            conversation_id,
        )
        handover_func = _TOOL_FUNCTIONS["request_human_handover"]
        await handover_func(
            db,
            conversation_id=conversation_id,
            args={"reason": "Bot could not resolve the request after repeated tool calls."},
        )
        final_text = (
            "Sorry for the back and forth — I'm looping in a team member "
            "who'll take it from here shortly."
        )

    await _persist_bot_text_message(db, conversation_id=conversation_id, text=final_text)

    # --- Phase 6 addition: single dashboard live-push call. See design
    # note 6 at the top of this file for scope/rationale. ---
    await broadcast_new_message(
        business_id=business_id, conversation_id=conversation_id, text=final_text
    )

    return final_text