/**
 * Thin fetch wrapper for the backend's /api/* routes. The GET/POST/PATCH
 * helpers and JWT-header plumbing are complete boilerplate; the actual
 * endpoint-specific functions (getKpiSummary, listConversations, etc.)
 * are added in Phase 8, once backend/app/api/dashboard_routes.py (Phase 6)
 * defines the real routes and response shapes.
 *
 * >>> PHASE 8 TARGET (endpoint functions only) — see PROJECT_PLAN.md <<<
 */

const BASE_URL = "/api";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("jwt");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const apiGet = <T>(path: string) => request<T>(path);
export const apiPost = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });
export const apiPatch = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body) });

// TODO (Phase 8): add typed functions per endpoint once
// dashboard_routes.py's response shapes are finalized, e.g.:
//   export const getKpiSummary = (from: string, to: string) =>
//     apiGet<KpiSummary>(`/kpis/summary?from=${from}&to=${to}`);
//   export const listConversations = (status?: string) =>
//     apiGet<Conversation[]>(`/conversations${status ? `?status=${status}` : ""}`);
//   export const getConversationMessages = (id: string) =>
//     apiGet<Message[]>(`/conversations/${id}/messages`);
//   export const listOrders = () => apiGet<Order[]>("/orders");
//   export const listProducts = () => apiGet<Product[]>("/products");
// Define the matching TypeScript interfaces (KpiSummary, Conversation,
// Message, Order, Product) in this file too, mirroring the backend's
// Pydantic response models exactly.
