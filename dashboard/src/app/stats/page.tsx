"use client";

import { ArrowLeft, BarChart3, Globe, Webhook } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ApiConnectionBadge } from "@/components/ApiConnectionBadge";
import { fetchApiStats, getApiBaseUrl } from "@/lib/api";
import type { ApiUsageStats } from "@/lib/types";

function formatWhen(value: string): string {
  return new Date(value).toLocaleString();
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
      <p className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-zinc-100">{value}</p>
    </div>
  );
}

export default function StatsPage() {
  const [stats, setStats] = useState<ApiUsageStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchApiStats();
      setStats(data);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load API stats";
      setError(`${message} → ${getApiBaseUrl()}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), 15000);
    return () => clearInterval(interval);
  }, [load]);

  const sourceEntries = stats ? Object.entries(stats.by_source) : [];
  const endpointEntries = stats ? Object.entries(stats.by_endpoint) : [];

  return (
    <div className="app-shell">
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="top-bar shrink-0">
          <div className="flex min-w-0 items-center gap-2">
            <Link href="/" className="icon-btn" aria-label="Back to dashboard">
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div className="min-w-0">
              <h1 className="text-sm font-semibold">API usage</h1>
              <p className="text-[11px] text-zinc-500">n8n, webhooks, and dashboard calls</p>
            </div>
          </div>
        </div>

        <div className="workspace-scroll px-4 py-5 lg:px-8">
          <div className="mx-auto w-full max-w-3xl space-y-5">
            {loading ? (
              <p className="text-sm text-zinc-500">Loading…</p>
            ) : stats ? (
              <>
                <div className="grid gap-3 sm:grid-cols-3">
                  <StatCard label="Total calls" value={stats.total} />
                  <StatCard label="Today" value={stats.today} />
                  <StatCard label="This week" value={stats.this_week} />
                </div>

                <section className="glass-panel rounded-2xl p-5">
                  <div className="mb-4 flex items-center gap-2">
                    <Webhook className="h-4 w-4 text-accent-glow" />
                    <h2 className="text-sm font-semibold">By source</h2>
                  </div>
                  {sourceEntries.length === 0 ? (
                    <p className="text-xs text-zinc-500">No API calls recorded yet.</p>
                  ) : (
                    <ul className="space-y-2 text-xs">
                      {sourceEntries.map(([source, count]) => (
                        <li
                          key={source}
                          className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2"
                        >
                          <span className="capitalize text-zinc-300">{source}</span>
                          <span className="font-mono text-zinc-400">{count}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>

                <section className="glass-panel rounded-2xl p-5">
                  <div className="mb-4 flex items-center gap-2">
                    <Globe className="h-4 w-4 text-accent-glow" />
                    <h2 className="text-sm font-semibold">Top endpoints</h2>
                  </div>
                  {endpointEntries.length === 0 ? (
                    <p className="text-xs text-zinc-500">No endpoint data yet.</p>
                  ) : (
                    <ul className="space-y-2 text-xs">
                      {endpointEntries.map(([endpoint, count]) => (
                        <li
                          key={endpoint}
                          className="flex items-center justify-between gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2"
                        >
                          <code className="truncate text-zinc-300">{endpoint}</code>
                          <span className="shrink-0 font-mono text-zinc-400">{count}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>

                <section className="glass-panel rounded-2xl p-5">
                  <div className="mb-4 flex items-center gap-2">
                    <BarChart3 className="h-4 w-4 text-accent-glow" />
                    <h2 className="text-sm font-semibold">Recent calls</h2>
                  </div>
                  {stats.recent.length === 0 ? (
                    <p className="text-xs text-zinc-500">No recent calls.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead className="text-zinc-500">
                          <tr>
                            <th className="pb-2 pr-3 font-medium">Time</th>
                            <th className="pb-2 pr-3 font-medium">Source</th>
                            <th className="pb-2 pr-3 font-medium">Endpoint</th>
                            <th className="pb-2 pr-3 font-medium">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {stats.recent.map((row) => (
                            <tr key={row.id} className="border-t border-white/5 text-zinc-300">
                              <td className="py-2 pr-3 whitespace-nowrap">{formatWhen(row.created_at)}</td>
                              <td className="py-2 pr-3 capitalize">{row.source}</td>
                              <td className="py-2 pr-3">
                                <code>{row.method} {row.endpoint}</code>
                              </td>
                              <td className="py-2 pr-3 font-mono">{row.status_code}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </>
            ) : null}

            {error && (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                {error}
              </div>
            )}
          </div>
        </div>
      </main>

      <ApiConnectionBadge compact />
    </div>
  );
}
