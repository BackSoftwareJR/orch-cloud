"use client";

import { motion } from "framer-motion";
import { Radio, Terminal } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";

import { useWebSocketLogs } from "@/hooks/useWebSocketLogs";

interface LiveTerminalProps {
  jobId: string | null;
  title?: string;
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

export function LiveTerminal({ jobId, title = "Live logs" }: LiveTerminalProps) {
  const { lines, connected, error } = useWebSocketLogs({ jobId, enabled: Boolean(jobId) });
  const containerRef = useRef<HTMLDivElement>(null);

  const renderedLines = useMemo(() => {
    return lines.split("\n").map((line, index) => (
      <div key={`${index}-${line.slice(0, 24)}`} className={`whitespace-pre-wrap ${classifyLine(line)}`}>
        {line || " "}
      </div>
    ));
  }, [lines]);

  useEffect(() => {
    const container = containerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [lines]);

  return (
    <section className="glass-panel flex h-full min-h-[320px] flex-col overflow-hidden rounded-3xl">
      <div className="flex items-center justify-between border-b border-white/5 px-5 py-3">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-accent-glow" />
          <span className="text-sm font-medium tracking-tight">{title}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <Radio
            className={`h-3 w-3 ${connected ? "text-emerald-400" : "text-zinc-600"}`}
          />
          <span className={connected ? "text-emerald-400" : "text-zinc-500"}>
            {jobId ? (connected ? "Streaming" : "Connecting…") : "No job selected"}
          </span>
        </div>
      </div>

      <div
        ref={containerRef}
        className="scrollbar-thin flex-1 overflow-y-auto bg-[#050508] px-4 py-3 font-mono text-[12px] leading-relaxed"
      >
        {!jobId ? (
          <p className="text-zinc-600">Select a job from the queue or history to stream logs.</p>
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

      {jobId && (
        <div className="border-t border-white/5 px-5 py-2 font-mono text-[10px] text-zinc-600">
          {jobId}
        </div>
      )}
    </section>
  );
}
