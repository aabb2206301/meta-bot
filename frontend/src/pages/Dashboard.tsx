/**
 * KPI overview — enquiries/orders/revenue trend charts, per-channel
 * breakdown, cost-per-conversation (from llm_call_log via kpi rollups).
 *
 * >>> PHASE 9 TARGET — implement once api/client.ts has getKpiSummary <<<
 *
 * TODO:
 * - Fetch GET /api/kpis/summary on mount (date range: default last 30
 *   days, add a simple range picker).
 * - Use recharts (already a dependency) for: a line chart of
 *   enquiries/orders over time, and a bar or pie chart of revenue by
 *   channel.
 * - Show top-line numbers (total enquiries, AI-resolved %, total
 *   revenue, avg response time) as stat cards above the charts.
 * - Loading and empty states — the seed script (Phase 7) should make
 *   this non-empty in a dev environment, but handle the zero-data case
 *   gracefully for a fresh business.
 */
export default function Dashboard() {
  return (
    <div>
      <h1>Dashboard</h1>
      <p>TODO (Phase 9): KPI charts — see file header for spec.</p>
    </div>
  );
}
