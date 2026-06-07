"use client";

import { fetchHealth, getApiBaseUrl } from "@/lib/api";
import { useEffect, useState } from "react";

type ConnectionStatus = "checking" | "connected" | "failed";

interface ApiConnectionBadgeProps {
  compact?: boolean;
}

export function ApiConnectionBadge({ compact = false }: ApiConnectionBadgeProps) {
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

  if (compact) {
    return (
      <div
        className="fixed right-3 top-3 z-50 lg:right-4 lg:top-4"
        title={`API: ${apiUrl} — ${status}`}
      >
        <span
          className={`inline-flex h-2.5 w-2.5 rounded-full ring-2 ring-[#0a0a0f] ${
            status === "connected"
              ? "bg-emerald-400"
              : status === "failed"
                ? "bg-red-400"
                : "bg-zinc-500 animate-pulse"
          }`}
        />
      </div>
    );
  }

  const label =
    status === "checking" ? "Checking…" : status === "connected" ? "API OK" : "API Failed";

  return (
    <div
      className={`fixed z-50 rounded-xl border px-3 py-2 text-xs shadow-lg backdrop-blur-sm ${
        status === "connected"
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
          : status === "failed"
            ? "border-red-500/30 bg-red-500/10 text-red-300"
            : "border-zinc-500/30 bg-zinc-500/10 text-zinc-400"
      } bottom-[calc(4.5rem+env(safe-area-inset-bottom))] right-3 lg:bottom-4 lg:right-4`}
    >
      <span className="font-medium">{label}</span>
    </div>
  );
}
