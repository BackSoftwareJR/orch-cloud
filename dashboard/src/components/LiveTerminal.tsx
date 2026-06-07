"use client";

import { motion } from "framer-motion";
import { Radio, Terminal } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useWebSocketLogs } from "@/hooks/useWebSocketLogs";

interface LiveTerminalProps {
  jobId: string | null;
  title?: string;
  /** When provided, uses shared stream instead of opening a new WebSocket. */
  lines?: string;
  connected?: boolean;
  error?: string | null;
}

function classifyLine(line: string): string {
  const lower = line.toLowerCase();
  if (lower.includes("error") || lower.includes("exception") || lower.includes("failed")) {
    return "terminal-line-error";
  }
  if (lower.includes("warn")) return "terminal-line-warn";
  if (lower.includes("info") || lower.includes("[system]")) return "terminal-line-info";
  if (lower.includes("success") || lower.includes("completed")) return "terminal-line-success";
  if (line.startsWith("Command:") || line.startsWith("Started:")) return "terminal-line-dim";
  return "text-zinc-300";
}

export function LiveTerminal({
  jobId,
  title = "Live logs",
  lines: externalLines,
  connected: externalConnected,
  error: externalError,
}: LiveTerminalProps) {
  const useExternal = externalLines !== undefined;
  const internal = useWebSocketLogs({
    jobId,
    enabled: Boolean(jobId) && !useExternal,
  });

  const lines = useExternal ? externalLines : internal.lines;
  const connected = useExternal ? (externalConnected ?? false) : internal.connected;
  const error = useExternal ? externalError : internal.error;

  const containerRef = useRef<HTMLDivElement>(null);
  const [stickToBottom, setStickToBottom] = useState(true);

  const scrollToBottom = useCallback(() => {
    const container = containerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, []);

  const handleScroll = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    setStickToBottom(distanceFromBottom < 60);
  }, []);

  const renderedLines = useMemo(() => {
    return lines.split("\n").map((line, index) => (
      <div key={`${index}-${line.slice(0, 24)}`} className={`whitespace-pre-wrap break-all ${classifyLine(line)}`}>
        {line || " "}
      </div>
    ));
  }, [lines]);

  useEffect(() => {
    if (stickToBottom) {
      scrollToBottom();
    }
  }, [lines, stickToBottom, scrollToBottom]);

  return (
    <section className="relative flex h-full min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-white/[0.06] bg-[#050508] lg:rounded-2xl">
      <div className="flex shrink-0 items-center justify-between border-b border-white/5 px-3 py-2 lg:px-4">
        <div className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5 text-accent-glow" />
          {title ? <span className="text-xs font-medium tracking-tight">{title}</span> : null}
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          <Radio className={`h-3 w-3 ${connected ? "text-emerald-400 animate-pulse" : "text-zinc-600"}`} />
          <span className={connected ? "text-emerald-400" : "text-zinc-500"}>
            {jobId ? (connected ? "Streaming" : "Connecting…") : "No job"}
          </span>
        </div>
      </div>

      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="workspace-scroll terminal-scroll scrollbar-thin px-3 py-2 font-mono text-[10px] leading-relaxed touch-pan-y lg:text-[11px]"
      >
        {!jobId ? (
          <p className="text-zinc-600">Select a task to stream logs.</p>
        ) : renderedLines.length === 0 ? (
          <motion.p
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ repeat: Infinity, duration: 2 }}
            className="text-zinc-600"
          >
            Waiting for log output…
          </motion.p>
        ) : (
          renderedLines
        )}
        {error && <p className="mt-2 text-red-400">{error}</p>}
      </div>

      {!stickToBottom && (
        <button
          type="button"
          onClick={() => {
            setStickToBottom(true);
            scrollToBottom();
          }}
          className="absolute bottom-2 left-1/2 z-10 -translate-x-1/2 rounded-full border border-white/10 bg-zinc-900/90 px-3 py-1 text-[10px] text-zinc-300 shadow-lg backdrop-blur-sm"
        >
          ↓ Latest output
        </button>
      )}
    </section>
  );
}
