"use client";

import { fetchHealth, getApiBaseUrl } from "@/lib/api";
import { useEffect, useState } from "react";

type ConnectionStatus = "checking" | "connected" | "failed";

export function ApiConnectionBadge() {
  const [status, setStatus] = useState<ConnectionStatus>("checking");
  const [detail, setDetail] = useState<string>("");
  const apiUrl = getApiBaseUrl();

  useEffect(() => {
    let cancelled = false;

    fetchHealth()
      .then(() => {
        if (!cancelled) {
          setStatus("connected");
          setDetail("");
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setStatus("failed");
          setDetail(err instanceof Error ? err.message : "Network error");
        }
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
      className={`fixed bottom-4 right-4 z-50 max-w-xs rounded-xl border px-3 py-2 text-xs shadow-lg backdrop-blur-sm ${colorClass}`}
    >
      <span className="font-medium">{label}</span>
      <span className="mt-0.5 block break-all opacity-80">{apiUrl}</span>
      {detail && <span className="mt-1 block break-all opacity-70">{detail}</span>}
    </div>
  );
}
