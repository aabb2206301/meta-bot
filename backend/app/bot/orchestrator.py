"""
The conversation loop — this is the heart of the bot. Ties together
llm/factory.py, tools/registry.py + tools/*.py, and db/models.py.

>>> PHASE 4 TARGET — implement per PROJECT_PLAN.md section 1 & 4 <<<

Reference loop (from the plan, section 4, in plain terms):
    1. Load last settings.max_history_messages messages for this
       conversation from the `messages` table, oldest first.
    2. Call llm.chat(history + new_message, tools=TOOLS).
    3. If response.tool_calls: execute each via the matching function in
       tools/ (use tools/registry.py's TOOL_DISPATCH_MAP to resolve name
       -> function rather than an if/elif chain), append the tool
       result to the message list as a `role: "tool"` message, call the
       LLM again — it now has the result and can either call another
       tool or write a reply.
    4. Once the LLM returns plain text (no more tool_calls), send it to
       the customer via the originating channel's send() function
       (channels/*.py, Phase 5), and persist BOTH the tool
       calls/results and the final text as rows in `messages`.

TODO:
- async def handle_incoming_message(db, *, conversation_id: str, customer_id: str,
        business_id: str, channel: str, text: str, external_message_id: str) -> str:
    Implements the loop above. Returns the final text reply (the caller —
    a channel webhook handler — is responsible for actually sending it).
    - Insert the incoming customer message as a `messages` row FIRST
      (sender='customer'), using external_message_id for the
      UNIQUE(conversation_id, external_message_id) de-dup constraint —
      if the insert violates uniqueness, this is a Meta webhook retry;
      return early without calling the LLM again.
    - Build the LLM's system message via bot/prompts.build_system_prompt.
    - Get the provider via llm/factory.get_llm_provider() (consider:
      does this belong here per-call, or once at app startup and reused?
      Pick one and document it).
    - Dispatch tool calls: TOOL_DISPATCH_MAP name -> function, calling
      each with (db, business_id=..., conversation_id=..., customer_id=...,
      args=tool_call.arguments) as applicable per that tool's signature —
      signatures differ slightly across tools/*.py, check each.
    - Log every LLM call to `llm_call_log` (provider, model, tokens,
      latency_ms) — this table exists specifically for this.
    - Cap the tool-call loop (e.g. max 5 rounds) so a confused model
      can't loop forever running up API cost.
- Keep channel-specific formatting (e.g. WhatsApp's message length
  limits) OUT of this file — this returns plain text; channels/*.py
  (Phase 5) is responsible for formatting/chunking before sending.
"""


async def handle_incoming_message(
    db,
    *,
    conversation_id: str,
    customer_id: str,
    business_id: str,
    channel: str,
    text: str,
    external_message_id: str,
) -> str:
    raise NotImplementedError("Phase 4: implement handle_incoming_message")
