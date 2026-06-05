"use client";

import { motion } from "framer-motion";
import { CheckCircle2, XCircle } from "lucide-react";
import type { ReactNode } from "react";

import type { Job } from "@/lib/types";

interface JobHistoryProps {
  jobs: Job[];
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
}

const statusConfig: Record<
  string,
  { label: string; className: string; icon?: ReactNode }
> = {
  COMPLETED: {
    label: "Completed",
    className: "text-emerald-400",
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
  },
  FAILED: {
    label: "Failed",
    className: "text-red-400",
    icon: <XCircle className="h-3.5 w-3.5" />,
  },
  CANCELLED: {
    label: "Cancelled",
    className: "text-zinc-400",
  },
  QUEUED: { label: "Queued", className: "text-amber-300" },
  RUNNING: { label: "Running", className: "text-sky-300" },
};

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function JobHistory({ jobs, selectedJobId, onSelectJob }: JobHistoryProps) {
  const history = jobs.filter(
    (job) =>
      job.status === "COMPLETED" ||
      job.status === "FAILED" ||
      job.status === "CANCELLED",
  );

  return (
    <section className="glass-panel rounded-3xl p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold tracking-tight">Run history</h3>
        <p className="text-xs text-zinc-500">{history.length} past runs</p>
      </div>

      {history.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-white/10 px-4 py-8 text-center text-sm text-zinc-500">
          No completed runs yet.
        </p>
      ) : (
        <div className="scrollbar-thin overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-white/5 text-xs uppercase tracking-wider text-zinc-500">
                <th className="pb-3 pr-4 font-medium">Status</th>
                <th className="pb-3 pr-4 font-medium">Task</th>
                <th className="pb-3 pr-4 font-medium">Level</th>
                <th className="pb-3 pr-4 font-medium">Started</th>
                <th className="pb-3 font-medium">Finished</th>
              </tr>
            </thead>
            <tbody>
              {history.map((job) => {
                const config = statusConfig[job.status] ?? statusConfig.FAILED;
                return (
                  <motion.tr
                    key={job.job_id}
                    onClick={() => onSelectJob(job.job_id)}
                    whileHover={{ backgroundColor: "rgba(255,255,255,0.03)" }}
                    className={`cursor-pointer border-b border-white/[0.03] transition ${
                      selectedJobId === job.job_id ? "bg-accent/5" : ""
                    }`}
                  >
                    <td className="py-3 pr-4">
                      <span
                        className={`inline-flex items-center gap-1.5 text-xs font-medium ${config.className}`}
                      >
                        {config.icon}
                        {config.label}
                      </span>
                    </td>
                    <td className="max-w-xs truncate py-3 pr-4 text-zinc-300">{job.task}</td>
                    <td className="py-3 pr-4 text-xs uppercase text-zinc-500">{job.level}</td>
                    <td className="py-3 pr-4 text-xs text-zinc-500">
                      {formatDateTime(job.started_at)}
                    </td>
                    <td className="py-3 text-xs text-zinc-500">
                      {formatDateTime(job.finished_at)}
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
