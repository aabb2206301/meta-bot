/**
 * Orders table — list, filter by status, manually update status.
 *
 * >>> PHASE 10 TARGET — implement once api/client.ts has listOrders <<<
 *
 * TODO:
 * - Table from GET /api/orders: customer name, product(s), total_amount,
 *   status, created_at. Filterable by status.
 * - Status change control (dropdown or buttons) calling
 *   PATCH /api/orders/{id} — reflect the update optimistically, roll
 *   back on failure.
 * - Click-through to the source conversation (Conversations.tsx) via
 *   the order's lead_id -> conversation_id, if you want that link;
 *   otherwise just show the customer contact info inline.
 */
export default function Orders() {
  return (
    <div>
      <h1>Orders</h1>
      <p>TODO (Phase 10): orders table — see file header for spec.</p>
    </div>
  );
}
