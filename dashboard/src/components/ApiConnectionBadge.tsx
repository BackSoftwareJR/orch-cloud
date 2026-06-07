"use client";

import { fetchHealth, getApiBaseUrl } from "@/lib/api";
import { useEffect, useState } from "react";

type ConnectionStatus = "checking" | "connected" | "failed";

export function ApiConnectionBadge() {
  const [status, setStatus] = useState<ConnectionStatus>("checking");
  const apiUrl = getApiBaseUrl();

  useEffect(() => {
    let cancelled = false;

    fetchHealth()
      .then(() => {
        if (!cancelled) setStatus("connected");
      })
      .catch(() => {
        if (!cancelled) setStatus("failed");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const label =
    status === "checking"
      ? "Checking API…"
      : status === "connected"
        ? "API Connected"
        : "API Connection Failed";

  const colorClass =
    status === "checking"
      ? "border-zinc-500/30 bg-zinc-500/10 text-zinc-400"
      : status === "connected"
        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
        : "border-red-500/30 bg-red-500/10 text-red-300";

  return (
    <div
      className={`fixed bottom-4 right-4 z-50 rounded-xl border px-3 py-2 text-xs shadow-lg backdrop-blur-sm ${colorClass}`}
      title={`Target: ${apiUrl}`}
    >
      <span className="font-medium">{label}</span>
      <span className="mt-0.5 block text-[10px] opacity-80">{apiUrl}</span>
    </div>
  );
}
