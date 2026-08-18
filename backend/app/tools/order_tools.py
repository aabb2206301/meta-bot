"""
create_order, update_order_status — the only two tools that write to
`orders` / `order_items`. This is the file PROJECT_PLAN.md section 4
gives a near-complete reference implementation for.

>>> PHASE 3 TARGET — implement per PROJECT_PLAN.md section 4 <<<

Reference (from the plan, for create_order):

    async def create_order(db, *, conversation_id: str, args: dict) -> dict:
        '''conversation_id comes from the webhook context, injected by the
        orchestrator — NEVER from the LLM's arguments. Only product_id,
        quantity, address, payment_method are LLM-supplied. This boundary
        matters: if you let the model supply conversation_id or
        customer_id, a manipulated conversation could write orders
        against someone else's account. Content parameters from the LLM,
        identity parameters from your own trusted context — always.'''
        conversation = await get_conversation(db, conversation_id)
        order = await db_create_order(
            db, customer_id=conversation.customer_id,
            product_id=args["product_id"], quantity=args["quantity"],
            address=args["address"], payment_method=args["payment_method"],
        )
        return {"order_id": str(order.id), "status": order.status}

TODO:
- Implement create_order as above. `db_create_order` / `get_conversation`
  are placeholders in the plan for whatever query helpers you write here
  — inline the queries directly in this file, there's no separate repo
  layer in this codebase.
- Before inserting, re-check stock via the same query check_stock uses
  (product_tools.py) and raise/return a clear error dict if
  stock_qty < quantity rather than creating an order the business can't
  fulfil.
- Create the matching OrderItem row(s) in the same transaction as the
  Order row — an order with quantity but no line item is a data bug.
- Decrement Product.stock_qty by the ordered quantity in the same
  transaction.
- async def update_order_status(db, *, customer_id: str, args: dict) -> dict:
    - args: order_id, status (both LLM-supplied).
    - Load the order, verify order.customer_id == customer_id (the
      trusted, orchestrator-injected identity) before allowing the
      update — this is the same trust-boundary rule as create_order,
      applied to reads instead of writes. Without this check a
      manipulated conversation could cancel or alter someone else's
      order by guessing/stating an order_id.
    - Return {"order_id", "status"}.
"""


async def create_order(db, *, conversation_id: str, args: dict) -> dict:
    raise NotImplementedError("Phase 3: implement create_order")


async def update_order_status(db, *, customer_id: str, args: dict) -> dict:
    raise NotImplementedError("Phase 3: implement update_order_status")
