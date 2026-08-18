"""
System prompt template(s) for the sales/order agent persona.

>>> PHASE 4 TARGET — write per PROJECT_PLAN.md section 1 & 4 <<<

TODO:
- def build_system_prompt(business_name: str) -> str:
    Write the persona: friendly sales agent for `business_name`, sells
    via WhatsApp/Instagram/Facebook, must use search_products/search_faqs
    before answering product or policy questions rather than guessing,
    must confirm product+quantity+address+payment method before calling
    create_order, and must call request_human_handover when it can't
    confidently continue (angry customer, ambiguous request after 2
    clarifying attempts, anything outside the tool set like refunds
    negotiation). COD-only — the tool schema in tools/registry.py already
    enforces this via the payment_method enum, but say it in the prompt
    too so the model doesn't try to offer other options in plain text.
- Keep this to one function for now; if you need per-channel variations
  later (e.g. shorter replies for Instagram DMs), add a `channel`
  parameter rather than duplicating the whole prompt.
"""


def build_system_prompt(business_name: str) -> str:
    raise NotImplementedError("Phase 4: write build_system_prompt")
