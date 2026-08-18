/**
 * Conversation list + detail view, with live updates over the
 * dashboard websocket (api/websocket.py, Phase 6).
 *
 * >>> PHASE 9 TARGET — implemented <<<
 *
 * Layout:
 *  - Left: filterable conversation list (status + channel). Handed-over
 *    conversations are highlighted as the "needs a human" queue.
 *  - Right: message thread for the selected conversation. Customer
 *    messages align left; bot/staff align right. Messages with
 *    tool_calls / tool_results render as a collapsed, muted "system"
 *    line (toggleable to inspect the raw JSON) — they aren't
 *    conversation content, just a debugging breadcrumb.
 *  - Live updates: WebSocket to /ws/conversations?token=...; new
 *    `message` events for the currently-open conversation are appended
 *    in place. A "● live / ○ offline" indicator reflects the socket
 *    state.
 *  - Reply box: posts to POST /api/conversations/{id}/messages
 *    (endpoint added in Phase 9 to dashboard_routes.py — see that
 *    file's known-limitation note about outbound channel delivery).
 *    The sender's own dashboard dedupes the post-send WS echo by
 *    (sender, content, recent) so a staff message only appears once.
 */
import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";

import {
  getConversationMessages,
  getToken,
  listConversations,
  postStaffMessage,
  type ConversationListItem,
  type ConversationMessage,
} from "../api/client";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "handed_over", label: "Handed over" },
  { value: "closed", label: "Closed" },
];

const CHANNEL_OPTIONS = [
  { value: "", label: "All channels" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "instagram", label: "Instagram" },
  { value: "facebook", label: "Facebook" },
];

const PAGE_SIZE = 20;

type WsEvent = {
  type: string;
  conversation_id?: string;
  sender?: string;
  content?: string;
  [k: string]: unknown;
};

const STAFF_DEDUP_WINDOW_MS = 5000;

export default function Conversations() {
  const [statusFilter, setStatusFilter] = useState("");
  const [channelFilter, setChannelFilter] = useState("");
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const selectedIdRef = useRef<string | null>(null);
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  // Keep ref in sync with state so the WS callback (closed-over) can
  // read the currently-selected conversation without re-opening the
  // socket on every selection change.
  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  // Load conversation list when filters change.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoadingList(true);
      setListError(null);
      try {
        const params: { status?: string; channel?: string; page: number; page_size: number } = {
          page: 1,
          page_size: PAGE_SIZE,
        };
        if (statusFilter) params.status = statusFilter;
        if (channelFilter) params.channel = channelFilter;
        const resp = await listConversations(params);
        if (cancelled) return;
        setConversations(resp.items);
        // Auto-select the first row on initial load, or when the
        // currently-selected conversation is no longer in the filtered
        // list (filters can hide it). Switching filters does not clear
        // the selection if the conversation is still visible.
        setSelectedId((current) => {
          if (current && resp.items.some((c) => c.id === current)) return current;
          return resp.items[0]?.id ?? null;
        });
      } catch (e) {
        if (!cancelled) setListError((e as Error).message);
      } finally {
        if (!cancelled) setLoadingList(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [statusFilter, channelFilter]);

  // Load message thread when selection changes.
  useEffect(() => {
    if (!selectedId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    async function load() {
      setLoadingMessages(true);
      try {
        const resp = await getConversationMessages(selectedId!);
        if (cancelled) return;
        setMessages(resp.messages);
      } catch {
        if (!cancelled) setMessages([]);
      } finally {
        if (!cancelled) setLoadingMessages(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  // Auto-scroll the thread to the bottom on new messages.
  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, selectedId]);

  // Open the dashboard WebSocket once on mount. The token is passed as
  // a query param because browsers can't set headers on the WS
  // handshake (api/websocket.py documents this).
  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/ws/conversations?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);

    ws.onmessage = (evt) => {
      let data: WsEvent;
      try {
        data = JSON.parse(evt.data) as WsEvent;
      } catch {
        return;
      }
      if (data.type !== "message") return;
      if (data.conversation_id !== selectedIdRef.current) return;
      if (typeof data.content !== "string" || typeof data.sender !== "string") return;

      const live: ConversationMessage = {
        id: `live-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        sender: data.sender,
        content: data.content,
        tool_calls: null,
        tool_results: null,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => {
        // Dedup: the server's broadcast_new_message fires for every
        // staff message too, so a sender's own optimistic append will
        // see a duplicate echo over the WS. Drop it if the last
        // message matches (sender, content) within a short window.
        const last = prev[prev.length - 1];
        if (last && last.sender === live.sender && last.content === live.content) {
          const ageMs = Date.now() - new Date(last.created_at).getTime();
          if (ageMs >= 0 && ageMs < STAFF_DEDUP_WINDOW_MS) return prev;
        }
        return [...prev, live];
      });
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, []);

  async function sendReply() {
    if (!selectedId || !replyText.trim() || sending) return;
    setSending(true);
    try {
      const msg = await postStaffMessage(selectedId, replyText.trim());
      setMessages((prev) => [...prev, msg]);
      setReplyText("");
    } catch (e) {
      // Use a simple alert for now — the project doesn't have a toast
      // system. Phase 9 keeps it explicit.
      window.alert((e as Error).message);
    } finally {
      setSending(false);
    }
  }

  const selectedConv = conversations.find((c) => c.id === selectedId);

  return (
    <div style={pageStyle}>
      <aside style={listStyle}>
        <h2 style={{ margin: 0, marginBottom: 12, fontSize: 16 }}>Conversations</h2>
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={selectStyle}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            style={selectStyle}
          >
            {CHANNEL_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        {loadingList ? (
          <p style={{ color: "#666", fontSize: 13 }}>Loading…</p>
        ) : listError ? (
          <p style={{ color: "crimson", fontSize: 13 }}>{listError}</p>
        ) : conversations.length === 0 ? (
          <p style={{ color: "#666", fontSize: 13 }}>No conversations match these filters.</p>
        ) : (
          <ul style={listUlStyle}>
            {conversations.map((c) => (
              <li
                key={c.id}
                onClick={() => setSelectedId(c.id)}
                style={listItemStyle(c.id === selectedId, c.status === "handed_over")}
              >
                <div style={listItemHeaderStyle}>
                  <strong style={{ fontSize: 14 }}>{c.customer_name || "(unknown)"}</strong>
                  <StatusBadge status={c.status} />
                </div>
                <div style={listItemMetaStyle}>
                  {c.channel} · {timeAgo(c.last_message_at)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <section style={threadStyle}>
        {!selectedId ? (
          <div style={emptyThreadStyle}>Select a conversation to view the thread.</div>
        ) : (
          <>
            <header style={threadHeaderStyle}>
              <div>
                <strong>{selectedConv?.customer_name || "(unknown)"}</strong>{" "}
                <span style={{ color: "#666", fontSize: 13 }}>
                  · {selectedConv?.channel}
                </span>
                {selectedConv && (
                  <span style={{ marginLeft: 8 }}>
                    <StatusBadge status={selectedConv.status} />
                  </span>
                )}
              </div>
              <span style={{ fontSize: 12, color: wsConnected ? "#10b981" : "#999" }}>
                {wsConnected ? "● live" : "○ offline"}
              </span>
            </header>
            <div style={threadBodyStyle}>
              {loadingMessages ? (
                <p style={{ color: "#666" }}>Loading…</p>
              ) : messages.length === 0 ? (
                <p style={{ color: "#666" }}>No messages yet.</p>
              ) : (
                messages.map((m) => <MessageRow key={m.id} msg={m} />)
              )}
              <div ref={threadEndRef} />
            </div>
            <footer style={replyFooterStyle}>
              <input
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    void sendReply();
                  }
                }}
                placeholder="Reply as staff…"
                style={replyInputStyle}
                disabled={sending}
              />
              <button
                onClick={() => void sendReply()}
                disabled={!replyText.trim() || sending}
                style={sendButtonStyle(!replyText.trim() || sending)}
              >
                {sending ? "Sending…" : "Send"}
              </button>
            </footer>
          </>
        )}
      </section>
    </div>
  );
}

function MessageRow({ msg }: { msg: ConversationMessage }) {
  // Render tool calls/results as a collapsed "system" line, not a chat
  // bubble. Per the Phase 9 plan: these aren't conversation content.
  if (msg.tool_calls != null || msg.tool_results != null) {
    return <SystemLine msg={msg} />;
  }

  const isCustomer = msg.sender === "customer";
  const isStaff = msg.sender === "staff";
  const isBot = msg.sender === "bot";
  const align: CSSProperties["justifyContent"] = isCustomer ? "flex-start" : "flex-end";
  const bg = isCustomer ? "#f1f5f9" : isStaff ? "#dbeafe" : isBot ? "#e0f2fe" : "#e5e7eb";
  const label = isCustomer ? "Customer" : isStaff ? "Staff" : isBot ? "Bot" : msg.sender;

  return (
    <div style={{ display: "flex", justifyContent: align, marginBottom: 8 }}>
      <div style={{ maxWidth: "70%" }}>
        <div style={messageMetaStyle}>
          {label} · {formatTime(msg.created_at)}
        </div>
        <div
          style={{
            background: bg,
            padding: "8px 12px",
            borderRadius: 8,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            fontSize: 14,
          }}
        >
          {msg.content}
        </div>
      </div>
    </div>
  );
}

function SystemLine({ msg }: { msg: ConversationMessage }) {
  const [open, setOpen] = useState(false);
  const summary =
    msg.tool_calls != null
      ? summarizeToolCalls(msg.tool_calls as unknown)
      : "tool result";

  return (
    <div style={systemLineWrapStyle}>
      <button onClick={() => setOpen((o) => !o)} style={systemLineButtonStyle} title="Toggle tool details">
        <span style={{ marginRight: 4 }}>{open ? "▼" : "▶"}</span>
        <span>🔧 {summary}</span>
      </button>
      {open && (
        <pre style={systemPreStyle}>
{JSON.stringify({ tool_calls: msg.tool_calls, tool_results: msg.tool_results }, null, 2)}
        </pre>
      )}
    </div>
  );
}

function summarizeToolCalls(j: unknown): string {
  // OpenAI tool-call shape: [{ id, type, function: { name, arguments } }, ...]
  if (Array.isArray(j) && j.length > 0) {
    const first = j[0] as { function?: { name?: string } };
    const name = first?.function?.name;
    if (name) return j.length === 1 ? `tool call: ${name}` : `tool call: ${name} (+${j.length - 1})`;
  }
  return "tool call";
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "handed_over"
      ? "#b45309"
      : status === "open"
      ? "#1d4ed8"
      : status === "closed"
      ? "#4b5563"
      : "#4b5563";
  const bg =
    status === "handed_over"
      ? "#fef3c7"
      : status === "open"
      ? "#dbeafe"
      : status === "closed"
      ? "#e5e7eb"
      : "#e5e7eb";
  return (
    <span
      style={{
        background: bg,
        color,
        padding: "2px 6px",
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 600,
        textTransform: "capitalize",
      }}
    >
      {status.replace("_", " ")}
    </span>
  );
}

function formatTime(s: string): string {
  const d = new Date(s);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function timeAgo(s: string): string {
  const d = new Date(s);
  const ms = Date.now() - d.getTime();
  if (isNaN(ms)) return "";
  const m = Math.floor(ms / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.floor(h / 24);
  return `${days}d ago`;
}

const pageStyle: CSSProperties = {
  display: "flex",
  gap: 16,
  height: "calc(100vh - 48px)",
};

const listStyle: CSSProperties = {
  width: 320,
  borderRight: "1px solid #e5e5e5",
  padding: 12,
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
};

const selectStyle: CSSProperties = {
  flex: 1,
  padding: "4px 8px",
  border: "1px solid #ddd",
  borderRadius: 4,
  fontSize: 13,
  background: "#fff",
};

const listUlStyle: CSSProperties = {
  listStyle: "none",
  padding: 0,
  margin: 0,
  overflow: "auto",
  flex: 1,
};

function listItemStyle(isSelected: boolean, isHandedOver: boolean): CSSProperties {
  // Handed-over rows get a yellow background as the "needs a human"
  // queue. Selection still wins, so the active row is unambiguous.
  const background = isSelected
    ? "#eef2ff"
    : isHandedOver
    ? "#fffbe6"
    : "#fff";
  const borderColor = isHandedOver && !isSelected ? "#facc15" : "#eee";
  return {
    padding: 10,
    border: `1px solid ${borderColor}`,
    borderRadius: 6,
    marginBottom: 6,
    cursor: "pointer",
    background,
  };
}

const listItemHeaderStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: 8,
};

const listItemMetaStyle: CSSProperties = {
  fontSize: 12,
  color: "#666",
  marginTop: 4,
  textTransform: "capitalize",
};

const threadStyle: CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  background: "#fff",
  border: "1px solid #eee",
  borderRadius: 8,
  overflow: "hidden",
};

const threadHeaderStyle: CSSProperties = {
  padding: "12px 16px",
  borderBottom: "1px solid #eee",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  background: "#fafafa",
};

const threadBodyStyle: CSSProperties = {
  flex: 1,
  padding: 16,
  overflow: "auto",
  display: "flex",
  flexDirection: "column",
  background: "#fff",
};

const emptyThreadStyle: CSSProperties = {
  flex: 1,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: "#666",
};

const messageMetaStyle: CSSProperties = {
  fontSize: 11,
  color: "#666",
  marginBottom: 2,
};

const replyFooterStyle: CSSProperties = {
  borderTop: "1px solid #eee",
  padding: 12,
  display: "flex",
  gap: 8,
  background: "#fafafa",
};

const replyInputStyle: CSSProperties = {
  flex: 1,
  padding: "8px 12px",
  border: "1px solid #ddd",
  borderRadius: 4,
  fontSize: 14,
  background: "#fff",
};

function sendButtonStyle(disabled: boolean): CSSProperties {
  return {
    padding: "8px 16px",
    background: disabled ? "#9ca3af" : "#111",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    cursor: disabled ? "default" : "pointer",
    fontSize: 14,
  };
}

const systemLineWrapStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  marginBottom: 6,
};

const systemLineButtonStyle: CSSProperties = {
  background: "transparent",
  border: "none",
  color: "#999",
  fontSize: 12,
  cursor: "pointer",
  padding: 4,
};

const systemPreStyle: CSSProperties = {
  background: "#f8f8f8",
  border: "1px solid #eee",
  borderRadius: 4,
  padding: 8,
  fontSize: 11,
  maxWidth: "80%",
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
  marginTop: 4,
};
