/**
 * KPI overview — enquiries/orders/revenue trend charts, per-channel
 * breakdown.
 *
 * >>> PHASE 9 TARGET — implemented against api/client.ts's getKpiSummary <<<
 *
 * What it does:
 *  - Fetches GET /api/kpis/summary on mount + whenever the range changes.
 *  - Four stat cards on top: total enquiries, AI-resolved %, total
 *    revenue, avg response time.
 *  - Two recharts: a line chart of enquiries + AI-resolved + orders over
 *    time, and a bar chart of revenue by channel.
 *  - Simple range picker: Last 7 / 30 / 90 days.
 *  - Loading state, error state, and a graceful empty/zero-data state
 *    for fresh businesses.
 *
 * Channel-revenue breakdown note: kpi_daily_snapshot rows already have a
 * channel column, and the KPI endpoint accepts a `?channel=` filter. We
 * make one main call + three channel-filtered calls in parallel so the
 * bar chart can show per-channel revenue without a separate endpoint.
 * A failed channel call is non-fatal — its slot renders as 0.
 */
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getKpiSummary, type KpiSummaryResponse } from "../api/client";

type RangeDays = 7 | 30 | 90;

const RANGE_OPTIONS: { label: string; value: RangeDays }[] = [
  { label: "Last 7 days", value: 7 },
  { label: "Last 30 days", value: 30 },
  { label: "Last 90 days", value: 90 },
];

const CHANNELS = ["whatsapp", "instagram", "facebook"] as const;
const CHANNEL_LABELS: Record<(typeof CHANNELS)[number], string> = {
  whatsapp: "WhatsApp",
  instagram: "Instagram",
  facebook: "Facebook",
};

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function rangeFor(days: RangeDays): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - (days - 1));
  return { from: isoDate(from), to: isoDate(to) };
}

function formatINR(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

function shortDate(s: string): string {
  // "2026-08-01" -> "Aug 1"
  const parts = s.split("-");
  if (parts.length !== 3) return s;
  const m = parseInt(parts[1], 10);
  const d = parseInt(parts[2], 10);
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  if (isNaN(m) || isNaN(d)) return s;
  return `${months[m - 1]} ${d}`;
}

interface ChannelRevenue {
  channel: string;
  revenue: number;
}

export default function Dashboard() {
  const [rangeDays, setRangeDays] = useState<RangeDays>(30);
  const [data, setData] = useState<KpiSummaryResponse | null>(null);
  const [revenueByChannel, setRevenueByChannel] = useState<ChannelRevenue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      const { from, to } = rangeFor(rangeDays);
      try {
        // Main call (unfiltered totals + daily series) is required; the
        // three channel-filtered calls are best-effort and default to 0
        // on failure so the bar chart still renders.
        const [main, ...channelResults] = await Promise.all([
          getKpiSummary({ from, to }),
          ...CHANNELS.map((ch) =>
            getKpiSummary({ from, to, channel: ch }).catch(() => null)
          ),
        ]);
        if (cancelled) return;
        setData(main);
        setRevenueByChannel(
          CHANNELS.map((ch, i) => ({
            channel: CHANNEL_LABELS[ch],
            revenue: channelResults[i]?.summary.revenue ?? 0,
          }))
        );
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
  }, [rangeDays]);

  const summary = data?.summary;
  const daily = data?.daily ?? [];

  const aiResolvedPct = useMemo(() => {
    if (!summary || summary.enquiries_count === 0) return 0;
    return Math.round((summary.ai_resolved_count / summary.enquiries_count) * 100);
  }, [summary]);

  const hasAnyData =
    !!summary && (summary.enquiries_count > 0 || summary.orders_count > 0 || summary.revenue > 0);

  if (loading && !data) {
    return (
      <div>
        <h1>Dashboard</h1>
        <p>Loading…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1>Dashboard</h1>
        <RangePicker value={rangeDays} onChange={setRangeDays} />
        <p style={{ color: "crimson" }}>Failed to load: {error}</p>
      </div>
    );
  }

  if (!hasAnyData) {
    return (
      <div>
        <h1 style={{ marginBottom: 16 }}>Dashboard</h1>
        <RangePicker value={rangeDays} onChange={setRangeDays} />
        <div style={emptyStateStyle}>
          <p style={{ marginBottom: 8, fontWeight: 500 }}>No data for this period yet.</p>
          <p style={{ fontSize: 13, color: "#666" }}>
            Once the bot starts handling conversations and the seed script runs,
            you&apos;ll see KPIs here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ marginBottom: 16 }}>Dashboard</h1>
      <RangePicker value={rangeDays} onChange={setRangeDays} />

      <div style={statRowStyle}>
        <StatCard label="Enquiries" value={summary!.enquiries_count.toLocaleString()} />
        <StatCard label="AI-resolved" value={`${aiResolvedPct}%`} />
        <StatCard label="Revenue" value={formatINR(summary!.revenue)} />
        <StatCard
          label="Avg response time"
          value={
            summary!.avg_response_seconds == null
              ? "—"
              : `${Math.round(summary!.avg_response_seconds)}s`
          }
        />
      </div>

      <div style={chartRowStyle}>
        <div style={cardStyle}>
          <h3 style={cardTitleStyle}>Enquiries &amp; orders over time</h3>
          <div style={chartContainerStyle}>
            <ResponsiveContainer>
              <LineChart data={daily} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="date" tickFormatter={shortDate} fontSize={12} />
                <YAxis yAxisId="left" fontSize={12} />
                <YAxis yAxisId="right" orientation="right" fontSize={12} />
                <Tooltip />
                <Legend />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="enquiries_count"
                  name="Enquiries"
                  stroke="#3b82f6"
                  dot={false}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="ai_resolved_count"
                  name="AI resolved"
                  stroke="#10b981"
                  dot={false}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="orders_count"
                  name="Orders"
                  stroke="#f59e0b"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div style={cardStyle}>
          <h3 style={cardTitleStyle}>Revenue by channel</h3>
          <div style={chartContainerStyle}>
            <ResponsiveContainer>
              <BarChart data={revenueByChannel} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis dataKey="channel" fontSize={12} />
                <YAxis fontSize={12} tickFormatter={(v) => `${v}`} />
                <Tooltip formatter={(v: number) => formatINR(v)} />
                <Bar dataKey="revenue" name="Revenue" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}

function RangePicker({
  value,
  onChange,
}: {
  value: RangeDays;
  onChange: (v: RangeDays) => void;
}) {
  return (
    <div style={{ marginBottom: 24, display: "flex", gap: 8 }}>
      {RANGE_OPTIONS.map((opt) => {
        const isActive = opt.value === value;
        return (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            disabled={isActive}
            style={rangeButtonStyle(isActive)}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={cardStyle}>
      <div style={{ fontSize: 13, color: "#666", marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 600 }}>{value}</div>
    </div>
  );
}

const cardStyle: CSSProperties = {
  background: "#fff",
  border: "1px solid #eee",
  borderRadius: 8,
  padding: 16,
};

const cardTitleStyle: CSSProperties = {
  margin: 0,
  marginBottom: 12,
  fontSize: 14,
  fontWeight: 600,
};

const statRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(4, 1fr)",
  gap: 16,
  marginBottom: 24,
};

const chartRowStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: 16,
};

const chartContainerStyle: CSSProperties = {
  width: "100%",
  height: 280,
};

const emptyStateStyle: CSSProperties = {
  padding: 32,
  border: "1px dashed #ddd",
  borderRadius: 8,
  textAlign: "center",
  color: "#444",
  background: "#fafafa",
};

function rangeButtonStyle(isActive: boolean): CSSProperties {
  return {
    padding: "6px 12px",
    border: "1px solid #ddd",
    background: isActive ? "#111" : "#fff",
    color: isActive ? "#fff" : "#111",
    borderRadius: 4,
    cursor: isActive ? "default" : "pointer",
    fontSize: 13,
  };
}
