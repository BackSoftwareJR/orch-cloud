"use client";

import { CheckCircle2, Circle, Clock, Loader2, XCircle } from "lucide-react";

import type { Job, JobStatus, TaskListFilter } from "@/lib/types";

interface TaskListPanelProps {
  jobs: Job[];
  filter: TaskListFilter;
  selectedJobId: string | null;
  onFilterChange: (filter: TaskListFilter) => void;
  onSelectJob: (jobId: string) => void;
}

const FILTERS: { id: TaskListFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "active", label: "Active" },
  { id: "done", label: "Done" },
];

function statusIcon(status: JobStatus) {
  switch (status) {
    case "RUNNING":
      return <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-300" />;
    case "QUEUED":
      return <Clock className="h-3.5 w-3.5 text-amber-300" />;
    case "COMPLETED":
      return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />;
    case "FAILED":
      return <XCircle className="h-3.5 w-3.5 text-red-400" />;
    default:
      return <Circle className="h-3.5 w-3.5 text-zinc-500" />;
  }
}

function filterJobs(jobs: Job[], filter: TaskListFilter): Job[] {
  if (filter === "active") {
    return jobs.filter((job) => job.status === "QUEUED" || job.status === "RUNNING");
  }
  if (filter === "done") {
    return jobs.filter(
      (job) =>
        job.status === "COMPLETED" ||
        job.status === "FAILED" ||
        job.status === "CANCELLED",
    );
  }
  return jobs;
}

function previewTask(job: Job): string {
  const firstLine = job.task.split("\n")[0]?.trim() ?? job.task;
  return firstLine.length > 120 ? `${firstLine.slice(0, 117)}…` : firstLine;
}

export function TaskListPanel({
  jobs,
  filter,
  selectedJobId,
  onFilterChange,
  onSelectJob,
}: TaskListPanelProps) {
  const visible = filterJobs(jobs, filter);

  return (
    <aside className="glass-panel flex w-[300px] shrink-0 flex-col border-r border-white/[0.06]">
      <div className="border-b border-white/[0.06] px-4 py-4">
        <h3 className="text-sm font-semibold tracking-tight">Tasks</h3>
        <p className="text-xs text-zinc-500">{visible.length} shown</p>
        <div className="mt-3 flex gap-1 rounded-xl bg-black/30 p-1">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onFilterChange(item.id)}
              className={`flex-1 rounded-lg px-2 py-1.5 text-[11px] font-medium transition ${
                filter === item.id
                  ? "bg-white/10 text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="scrollbar-thin flex-1 overflow-y-auto p-2">
        {visible.length === 0 ? (
          <p className="px-3 py-10 text-center text-xs text-zinc-500">
            No tasks in this view.
          </p>
        ) : (
          visible.map((job) => (
            <button
              key={job.job_id}
              type="button"
              onClick={() => onSelectJob(job.job_id)}
              className={`mb-1 w-full rounded-2xl border px-3 py-3 text-left transition ${
                selectedJobId === job.job_id
                  ? "border-accent/40 bg-accent/10"
                  : "border-transparent bg-white/[0.02] hover:bg-white/[0.05]"
              }`}
            >
              <div className="mb-1.5 flex items-center gap-2">
                {statusIcon(job.status)}
                <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-400">
                  {job.status}
                </span>
                <span className="text-[10px] text-zinc-600">{job.level}</span>
              </div>
              <p className="line-clamp-2 text-xs leading-relaxed text-zinc-200">
                {previewTask(job)}
              </p>
              <p className="mt-1 font-mono text-[10px] text-zinc-600">
                {job.job_id.slice(0, 8)}…
              </p>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
