"use client";

import { motion } from "framer-motion";
import { Clock, Loader2, Play } from "lucide-react";

import type { Job } from "@/lib/types";

interface JobQueueProps {
  jobs: Job[];
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
}

const statusStyles: Record<string, string> = {
  QUEUED: "bg-amber-500/15 text-amber-300",
  RUNNING: "bg-sky-500/15 text-sky-300",
};

function formatRelativeTime(value: string): string {
  const date = new Date(value);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function JobQueue({ jobs, selectedJobId, onSelectJob }: JobQueueProps) {
  const active = jobs.filter((job) => job.status === "QUEUED" || job.status === "RUNNING");

  return (
    <section className="glass-panel rounded-3xl p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold tracking-tight">Active queue</h3>
          <p className="text-xs text-zinc-500">{active.length} jobs in flight</p>
        </div>
      </div>

      {active.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-white/10 px-4 py-8 text-center text-sm text-zinc-500">
          Queue is idle — trigger a task to start orchestration.
        </p>
      ) : (
        <div className="space-y-2">
          {active.map((job) => (
            <motion.button
              key={job.job_id}
              type="button"
              layout
              onClick={() => onSelectJob(job.job_id)}
              whileHover={{ x: 2 }}
              className={`flex w-full items-start gap-3 rounded-2xl border px-4 py-3 text-left transition ${
                selectedJobId === job.job_id
                  ? "border-accent/40 bg-accent/10"
                  : "border-white/5 bg-white/[0.02] hover:bg-white/[0.05]"
              }`}
            >
              <div className="mt-0.5">
                {job.status === "RUNNING" ? (
                  <Loader2 className="h-4 w-4 animate-spin text-sky-300" />
                ) : (
                  <Clock className="h-4 w-4 text-amber-300" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${statusStyles[job.status]}`}
                  >
                    {job.status}
                  </span>
                  <span className="text-[10px] uppercase tracking-wider text-zinc-500">
                    {job.level}
                  </span>
                </div>
                <p className="line-clamp-2 text-sm text-zinc-200">{job.task}</p>
                <p className="mt-1 font-mono text-[10px] text-zinc-500">
                  {job.job_id.slice(0, 8)}… · {formatRelativeTime(job.created_at)}
                </p>
              </div>
              <Play className="mt-1 h-3.5 w-3.5 shrink-0 text-zinc-600" />
            </motion.button>
          ))}
        </div>
      )}
    </section>
  );
}
