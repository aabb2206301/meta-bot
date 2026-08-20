/**
 * Thin fetch wrapper for the backend's /api/* routes, plus typed
 * endpoint functions and interfaces mirroring
 * backend/app/api/dashboard_routes.py's Pydantic/JSON response shapes
 * field-for-field.
 *
 * >>> PHASE 8 <<< — endpoint functions + interfaces implemented below.
 * >>> PHASE 9 (additive) <<< — postStaffMessage() added for the staff
 * reply box in Conversations.tsx. The matching endpoint
 * (POST /api/conversations/{id}/messages) was not present in Phase 6's
 * dashboard_routes.py and is added in this phase per the Phase 9
 * plan's "add one in this phase if it wasn't included in Phase 6"
 * note.
 */

// In prod (split Railway services) VITE_API_URL points at the backend's
// public URL, e.g. https://meta-bot-production-d1da.up.railway.app — set
// it as a build-time env var on the frontend service. Falls back to the
// relative /api path for local dev via Vite's dev-server proxy.
const BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : "/api";
const TOKEN_STORAGE_KEY = "jwt";

// ---------------------------------------------------------------------
// Token storage
// ---------------------------------------------------------------------

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

// ---------------------------------------------------------------------
// Base request helpers
// ---------------------------------------------------------------------

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
    if (res.status === 401) {
      // Token missing/expired/rejected — clear it so the next render's
      // isAuthenticated() check sends the user back to /login instead of
      // silently failing every subsequent request.
      clearToken();
    }
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // Response wasn't JSON — fall back to statusText.
    }
    throw new Error(`API ${path} failed (${res.status}): ${detail}`);
  }

  return res.json() as Promise<T>;
}

export const apiGet = <T>(path: string) => request<T>(path);
export const apiPost = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });
export const apiPatch = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body) });

function toQueryString(params: Record<string, string | number | boolean | undefined>): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) qs.set(key, String(value));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

// ---------------------------------------------------------------------
// Auth — mirrors POST /api/auth/login
// ---------------------------------------------------------------------

export interface StaffInfo {
  id: string;
  name: string;
  email: string;
  role: string; // "owner" | "agent"
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  staff: StaffInfo;
}

export const login = (email: string, password: string) =>
  apiPost<LoginResponse>("/auth/login", { email, password });

// ---------------------------------------------------------------------
// KPIs — mirrors GET /api/kpis/summary
// ---------------------------------------------------------------------

export interface KpiSummary {
  enquiries_count: number;
  ai_resolved_count: number;
  avg_response_seconds: number | null;
  orders_count: number;
  revenue: number;
}

export interface KpiDailyPoint {
  date: string; // ISO YYYY-MM-DD
  enquiries_count: number;
  ai_resolved_count: number;
  orders_count: number;
  revenue: number;
}

export interface KpiSummaryResponse {
  from: string;
  to: string;
  channel: string | null;
  summary: KpiSummary;
  daily: KpiDailyPoint[];
}

export const getKpiSummary = (params?: { from?: string; to?: string; channel?: string }) =>
  apiGet<KpiSummaryResponse>(`/kpis/summary${toQueryString(params ?? {})}`);

// ---------------------------------------------------------------------
// Conversations — mirrors GET /api/conversations,
// GET /api/conversations/{id}/messages, and (Phase 9)
// POST /api/conversations/{id}/messages
// ---------------------------------------------------------------------

export interface ConversationListItem {
  id: string;
  customer_name: string;
  channel: string; // "whatsapp" | "instagram" | "facebook"
  status: string; // "open" | "handed_over" | "closed"
  assigned_staff_id: string | null;
  started_at: string;
  last_message_at: string;
}

export interface ConversationListResponse {
  total: number;
  page: number;
  page_size: number;
  items: ConversationListItem[];
}

export const listConversations = (params?: {
  status?: string;
  channel?: string;
  page?: number;
  page_size?: number;
}) => apiGet<ConversationListResponse>(`/conversations${toQueryString(params ?? {})}`);

export interface ConversationMessage {
  id: string;
  sender: string; // "customer" | "bot" | "staff"
  content: string | null;
  tool_calls: unknown | null;
  tool_results: unknown | null;
  created_at: string;
}

export interface ConversationMessagesResponse {
  conversation_id: string;
  status: string;
  messages: ConversationMessage[];
}

export const getConversationMessages = (conversationId: string) =>
  apiGet<ConversationMessagesResponse>(`/conversations/${conversationId}/messages`);

// Phase 9 addition — mirrors the staff-reply endpoint added to
// dashboard_routes.py in this phase (see file header).
export interface StaffMessage {
  id: string;
  sender: string; // always "staff" — typed loosely to match the
  //                ConversationMessage sender union for reuse in the
  //                message thread.
  content: string;
  created_at: string;
}

export const postStaffMessage = (conversationId: string, content: string) =>
  apiPost<StaffMessage>(`/conversations/${conversationId}/messages`, { content });

// ---------------------------------------------------------------------
// Orders — mirrors GET /api/orders and PATCH /api/orders/{id}
// ---------------------------------------------------------------------

export interface OrderItemDetail {
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: number;
}

export interface OrderListItem {
  id: string;
  customer_name: string;
  status: string; // "pending" | "confirmed" | "fulfilled" | "cancelled"
  payment_method: string;
  address: string | null;
  total_amount: number;
  items: OrderItemDetail[];
  created_at: string;
  updated_at: string;
}

export interface OrderListResponse {
  total: number;
  page: number;
  page_size: number;
  items: OrderListItem[];
}

export const listOrders = (params?: { status?: string; page?: number; page_size?: number }) =>
  apiGet<OrderListResponse>(`/orders${toQueryString(params ?? {})}`);

export interface OrderStatusUpdateResponse {
  id: string;
  status: string;
}

export const updateOrderStatus = (orderId: string, status: string) =>
  apiPatch<OrderStatusUpdateResponse>(`/orders/${orderId}`, { status });

// ---------------------------------------------------------------------
// Products — mirrors GET/POST/PATCH /api/products
// ---------------------------------------------------------------------

export interface Product {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  price: number;
  currency: string;
  stock_qty: number;
  image_url: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ProductListResponse {
  total: number;
  page: number;
  page_size: number;
  items: Product[];
}

export const listProducts = (params?: {
  category?: string;
  is_active?: boolean;
  page?: number;
  page_size?: number;
}) => apiGet<ProductListResponse>(`/products${toQueryString(params ?? {})}`);

export interface ProductCreateInput {
  name: string;
  description?: string;
  category?: string;
  price: number;
  currency?: string;
  stock_qty?: number;
  image_url?: string;
  is_active?: boolean;
}

export type ProductUpdateInput = Partial<ProductCreateInput>;

export const createProduct = (body: ProductCreateInput) => apiPost<Product>("/products", body);

export const updateProduct = (productId: string, body: ProductUpdateInput) =>
  apiPatch<Product>(`/products/${productId}`, body);
