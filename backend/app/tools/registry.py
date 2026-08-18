"""
TOOLS — OpenAI-format function-calling schema, shared by every LLM
provider (Groq consumes it as-is; google_provider.py converts it to
Gemini's format internally). Complete in the boilerplate, taken directly
from PROJECT_PLAN.md section 4.

NOTE: the plan's folder structure (section 2) mentions `check_stock` in
product_tools.py and `update_order_status` in order_tools.py, but its
worked example (section 4) only shows 5 tools. Both are added below so
the registry matches the folder structure exactly. If Phase 3 decides
either tool is unnecessary, remove it here AND from the matching
tools/*.py file in the same change.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search the catalog by name, category, or description. Use whenever a customer asks about a product, price, or availability.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "Check current stock quantity for a specific product by ID. Use before confirming an order can be fulfilled.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_faqs",
            "description": "Search business FAQs — shipping, returns, policies.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "upsert_lead",
            "description": "Create or update the lead record for this conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["new", "qualified", "hot", "lost"]},
                    "product_interest_id": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Create an order once product, quantity, address, and payment method (COD only) are all confirmed with the customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "address": {"type": "string"},
                    "payment_method": {"type": "string", "enum": ["cod"]},
                },
                "required": ["product_id", "quantity", "address", "payment_method"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_order_status",
            "description": "Update the status of an existing order (e.g. when a customer asks to cancel, or staff confirms fulfillment). Only call this for orders belonging to the current conversation's customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "confirmed", "fulfilled", "cancelled"],
                    },
                },
                "required": ["order_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_human_handover",
            "description": "Flag the conversation for a staff member when the bot cannot confidently continue.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"],
            },
        },
    },
]

# Maps each tool's `name` to the module.function that implements it —
# used by bot/orchestrator.py (Phase 4) to dispatch a ToolCall without a
# long if/elif chain. Populated once Phase 3 implements the tool modules.
TOOL_DISPATCH_MAP = {
    "search_products": "app.tools.product_tools.search_products",
    "check_stock": "app.tools.product_tools.check_stock",
    "search_faqs": "app.tools.faq_tools.search_faqs",
    "upsert_lead": "app.tools.lead_tools.upsert_lead",
    "create_order": "app.tools.order_tools.create_order",
    "update_order_status": "app.tools.order_tools.update_order_status",
    "request_human_handover": "app.tools.handover_tools.request_human_handover",
}
