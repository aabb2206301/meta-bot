/**
 * Orders table — list, filter by status, manually update status.
 *
 * >>> PHASE 10 TARGET — implemented <<<
 *
 * What it does:
 *  - Paginated table from GET /api/orders: customer, items, total,
 *    status, created_at. Filterable by status.
 *  - Status change dropdown per row calling PATCH /api/orders/{id}.
 *    This is the staff/manual path — separate from the bot's
 *    tools/order_tools.py:update_order_status, but writes the same
 *    `status` column on the same `orders` row (one source of truth).
 *  - Optimistic status update: change the row's badge immediately,
 *    roll back if PATCH fails.
 *
 * Known gap (per Orders.tsx stub's TODO): the click-through to the
 * source conversation is omitted. The order response doesn't include
 * lead_id or conversation_id (the backend would need an extra join
 * to expose either), and the order's customer_id isn't exposed
 * either. So we show the customer's name + shipping address inline
 * instead, per the TODO's fallback.
 */
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import {
  listOrders,
  updateOrderStatus,
  type OrderListItem,
  type OrderListResponse,
} from "../api/client";

const PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "pending", label: "Pending" },
  { value: "confirmed", label: "Confirmed" },
  { value: "fulfilled", label: "Fulfilled" },
  { value: "cancelled", label: "Cancelled" },
];

const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
  pending: { bg: "#fef3c7", fg: "#b45309" },
  confirmed: { bg: "#dbeafe", fg: "#1d4ed8" },
  fulfilled: { bg: "#dcfce7", fg: "#15803d" },
  cancelled: { bg: "#fee2e2", fg: "#b91c1c" },
};

export default function Orders() {
  const [statusFilter, setStatusFilter] = useState("");
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const params: { status?: string; page: number; page_size: number } = {
          page,
          page_size: PAGE_SIZE,
        };
        if (statusFilter) params.status = statusFilter;
        const resp: OrderListResponse = await listOrders(params);
        if (cancelled) return;
        setOrders(resp.items);
        setTotal(resp.total);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [statusFilter, page]);

  async function changeStatus(orderId: string, originalStatus: string, newStatus: string) {
    if (originalStatus === newStatus) return;
    setUpdatingId(orderId);
    // Optimistic — flip the row in-place. On failure, restore just this
    // order's status so we don't trash the rest of the list.
    setOrders((prev) =>
      prev.map((o) => (o.id === orderId ? { ...o, status: newStatus } : o))
    );
    try {
      await updateOrderStatus(orderId, newStatus);
    } catch (e) {
      setOrders((prev) =>
        prev.map((o) => (o.id === orderId ? { ...o, status: originalStatus } : o))
      );
      window.alert((e as Error).message);
    } finally {
      setUpdatingId(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <h1 style={{ marginBottom: 16 }}>Orders</h1>

      <div style={toolbarStyle}>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          style={selectStyle}
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <span style={{ color: "#666", fontSize: 13 }}>
          {total} {total === 1 ? "order" : "orders"}
        </span>
      </div>

      {loading ? (
        <p style={{ color: "#666" }}>Loading…</p>
      ) : error ? (
        <p style={{ color: "crimson" }}>Failed to load: {error}</p>
      ) : orders.length === 0 ? (
        <div style={emptyStyle}>No orders match these filters.</div>
      ) : (
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>Customer</th>
              <th style={thStyle}>Items</th>
              <th style={{ ...thStyle, textAlign: "right" }}>Total</th>
              <th style={thStyle}>Status</th>
              <th style={thStyle}>Created</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id} style={trStyle}>
                <td style={tdStyle}>
                  <div style={{ fontWeight: 500 }}>{o.customer_name || "(unknown)"}</div>
                  {o.address && <div style={addressStyle}>{o.address}</div>}
                  <div style={paymentStyle}>
                    {o.payment_method ? `Pay on delivery (${o.payment_method.toUpperCase()})` : ""}
                  </div>
                </td>
                <td style={tdStyle}>
                  {o.items.length === 0 ? (
                    <span style={{ color: "#999" }}>—</span>
                  ) : (
                    <ul style={itemsListStyle}>
                      {o.items.map((it, i) => (
                        <li key={`${o.id}-${i}`}>
                          {it.quantity}× {it.product_name}
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
                <td style={{ ...tdStyle, textAlign: "right", whiteSpace: "nowrap", fontWeight: 500 }}>
                  {formatINR(o.total_amount)}
                </td>
                <td style={tdStyle}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <select
                      value={o.status}
                      onChange={(e) => changeStatus(o.id, o.status, e.target.value)}
                      disabled={updatingId === o.id}
                      style={statusSelectStyle(o.status)}
                    >
                      {(["pending", "confirmed", "fulfilled", "cancelled"] as const).map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                    {updatingId === o.id && (
                      <span style={{ fontSize: 11, color: "#999" }}>saving…</span>
                    )}
                  </div>
                </td>
                <td style={{ ...tdStyle, whiteSpace: "nowrap", color: "#666", fontSize: 13 }}>
                  {formatDateTime(o.created_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {totalPages > 1 && (
        <div style={paginationStyle}>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            style={pageButtonStyle(page === 1)}
          >
            ← Prev
          </button>
          <span style={{ fontSize: 13, color: "#666" }}>
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            style={pageButtonStyle(page === totalPages)}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}

function formatINR(amount: number): string {
  // Orders don't expose a currency in the response, so we default to
  // ₹ — the same default the products / seed data use.
  return `₹${amount.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function formatDateTime(s: string): string {
  const d = new Date(s);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const toolbarStyle: CSSProperties = {
  display: "flex",
  gap: 12,
  marginBottom: 16,
  alignItems: "center",
};

const selectStyle: CSSProperties = {
  padding: "6px 10px",
  border: "1px solid #ddd",
  borderRadius: 4,
  fontSize: 13,
  background: "#fff",
};

const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  background: "#fff",
  border: "1px solid #eee",
  borderRadius: 8,
  overflow: "hidden",
};

const thStyle: CSSProperties = {
  textAlign: "left",
  padding: "10px 12px",
  borderBottom: "2px solid #e5e5e5",
  fontSize: 12,
  color: "#666",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.03em",
  background: "#fafafa",
};

const trStyle: CSSProperties = {
  // hover state is set via :hover; can't do that in inline styles —
  // the row is already visually distinct enough with row borders.
};

const tdStyle: CSSProperties = {
  padding: "12px",
  borderBottom: "1px solid #f0f0f0",
  verticalAlign: "top",
  fontSize: 14,
};

const addressStyle: CSSProperties = {
  fontSize: 12,
  color: "#666",
  marginTop: 2,
  whiteSpace: "pre-wrap",
};

const paymentStyle: CSSProperties = {
  fontSize: 11,
  color: "#999",
  marginTop: 2,
};

const itemsListStyle: CSSProperties = {
  margin: 0,
  padding: 0,
  listStyle: "none",
};

function statusSelectStyle(status: string): CSSProperties {
  const c = STATUS_COLORS[status] ?? { bg: "#e5e7eb", fg: "#4b5563" };
  return {
    padding: "4px 8px",
    border: `1px solid ${c.bg}`,
    background: c.bg,
    color: c.fg,
    borderRadius: 4,
    fontSize: 12,
    fontWeight: 600,
    textTransform: "capitalize",
    cursor: "pointer",
  };
}

const emptyStyle: CSSProperties = {
  padding: 32,
  border: "1px dashed #ddd",
  borderRadius: 8,
  textAlign: "center",
  color: "#666",
  background: "#fafafa",
};

const paginationStyle: CSSProperties = {
  marginTop: 16,
  display: "flex",
  gap: 12,
  alignItems: "center",
  justifyContent: "flex-end",
};

function pageButtonStyle(disabled: boolean): CSSProperties {
  return {
    padding: "6px 12px",
    border: "1px solid #ddd",
    borderRadius: 4,
    background: disabled ? "#f3f4f6" : "#fff",
    color: disabled ? "#9ca3af" : "#111",
    cursor: disabled ? "default" : "pointer",
    fontSize: 13,
  };
}
