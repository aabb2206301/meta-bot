/**
 * Conversation list + detail view, with live updates over the
 * dashboard websocket (api/websocket.py, Phase 6).
 *
 * >>> PHASE 9 TARGET — implement once api/client.ts has listConversations
 * and getConversationMessages <<<
 *
 * TODO:
 * - Left panel: paginated list from GET /api/conversations, filterable
 *   by status (open/handed_over/closed) and channel. Highlight
 *   handed_over conversations — that's the "needs a human" queue.
 * - Right panel: message thread for the selected conversation from
 *   GET /api/conversations/{id}/messages, rendered as chat bubbles
 *   (customer left, bot/staff right). Render tool_calls/tool_results
 *   as a collapsed/muted "system" line rather than a chat bubble — they're
 *   useful for debugging but shouldn't look like conversation content.
 * - Open a WebSocket connection to /ws/conversations on mount; when a
 *   message event arrives for the currently-open conversation, append
 *   it live instead of requiring a refresh.
 * - A "reply as staff" input box, posting through whatever endpoint
 *   Phase 6 exposes for staff-authored messages (add one to
 *   dashboard_routes.py in this phase if it wasn't included in Phase 6 —
 *   flag it if so).
 */
export default function Conversations() {
  return (
    <div>
      <h1>Conversations</h1>
      <p>TODO (Phase 9): conversation list + live thread — see file header for spec.</p>
    </div>
  );
}
