"use client";

import { ChevronDown, ChevronUp, Terminal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { LiveTerminal } from "@/components/LiveTerminal";
import { TaskActionsBar } from "@/components/TaskActionsBar";
import { TaskChat } from "@/components/TaskChat";
import { TaskComposer } from "@/components/TaskComposer";
import {
  cancelJob,
  continueJob,
  fetchJobMessages,
  requeueJob,
  restartJob,
} from "@/lib/api";
import type { Job, JobMessage } from "@/lib/types";

interface TaskWorkspaceProps {
  job: Job | null;
  onJobUpdated: (job: Job) => void;
  onNewJob: (job: Job) => void;
}

function statusBadgeClass(status: Job["status"]): string {
  switch (status) {
    case "RUNNING":
      return "bg-sky-500/15 text-sky-300 ring-sky-500/30";
    case "QUEUED":
      return "bg-amber-500/15 text-amber-300 ring-amber-500/30";
    case "COMPLETED":
      return "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30";
    case "FAILED":
      return "bg-red-500/15 text-red-300 ring-red-500/30";
    default:
      return "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30";
  }
}

export function TaskWorkspace({ job, onJobUpdated, onNewJob }: TaskWorkspaceProps) {
  const [messages, setMessages] = useState<JobMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [terminalOpen, setTerminalOpen] = useState(true);
  const [actionBusy, setActionBusy] = useState(false);

  const loadMessages = useCallback(async (jobId: string) => {
    setLoadingMessages(true);
    try {
      const data = await fetchJobMessages(jobId);
      setMessages(data);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  useEffect(() => {
    if (!job) {
      setMessages([]);
      return;
    }
    void loadMessages(job.job_id);
    setTerminalOpen(job.status === "RUNNING" || job.status === "QUEUED");
  }, [job, loadMessages]);

  useEffect(() => {
    if (!job || job.status !== "RUNNING") return;
    const interval = setInterval(() => void loadMessages(job.job_id), 4000);
    return () => clearInterval(interval);
  }, [job, loadMessages]);

  if (!job) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
        <div className="mb-4 rounded-3xl border border-dashed border-white/10 px-8 py-10">
          <p className="text-sm font-medium text-zinc-300">Select a task to open the workspace</p>
          <p className="mt-2 max-w-md text-xs leading-relaxed text-zinc-500">
            Review conversation history, stream live logs, restart failed runs, requeue tasks,
            or continue with follow-up instructions — Cursor-style.
          </p>
        </div>
      </div>
    );
  }

  const canContinue =
    job.status === "COMPLETED" ||
    job.status === "FAILED" ||
    job.status === "CANCELLED";

  async function withBusy<T>(action: () => Promise<T>): Promise<T> {
    setActionBusy(true);
    try {
      return await action();
    } finally {
      setActionBusy(false);
    }
  }

  return (
    <section className="flex min-w-0 flex-1 flex-col">
      <header className="border-b border-white/[0.06] px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span
                className={`inline-flex rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ring-1 ring-inset ${statusBadgeClass(job.status)}`}
              >
                {job.status}
              </span>
              <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wider text-zinc-400">
                {job.level}
              </span>
              <span className="font-mono text-[10px] text-zinc-600">{job.job_id.slice(0, 8)}…</span>
            </div>
            <p className="line-clamp-2 text-sm text-zinc-300">{job.task.split("\n")[0]}</p>
            {job.error_message && (
              <p className="mt-2 text-xs text-red-400">{job.error_message}</p>
            )}
          </div>
          <TaskActionsBar
            job={job}
            busy={actionBusy}
            onRestart={async () => {
              const next = await withBusy(() => restartJob(job.job_id));
              onNewJob(next);
            }}
            onRequeue={async () => {
              const updated = await withBusy(() => requeueJob(job.job_id));
              onJobUpdated(updated);
              await loadMessages(updated.job_id);
            }}
            onCancel={async () => {
              const updated = await withBusy(() => cancelJob(job.job_id));
              onJobUpdated(updated);
              await loadMessages(updated.job_id);
            }}
          />
        </div>
      </header>

      <TaskChat messages={messages} loading={loadingMessages} />

      <div className="border-t border-white/[0.06]">
        <button
          type="button"
          onClick={() => setTerminalOpen((open) => !open)}
          className="flex w-full items-center justify-between px-5 py-2.5 text-left text-xs text-zinc-400 transition hover:bg-white/[0.02]"
        >
          <span className="inline-flex items-center gap-2 font-medium">
            <Terminal className="h-3.5 w-3.5" />
            Live terminal
          </span>
          {terminalOpen ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronUp className="h-4 w-4" />
          )}
        </button>
        {terminalOpen && (
          <div className="h-[240px] border-t border-white/[0.04] px-3 pb-3">
            <LiveTerminal jobId={job.job_id} title="" />
          </div>
        )}
      </div>

      <TaskComposer
        disabled={!canContinue || actionBusy}
        placeholder={
          canContinue
            ? "Continue this task — describe what to do next…"
            : job.status === "RUNNING"
              ? "Agent is running… wait for completion to continue"
              : "Task is queued — follow-up available after completion"
        }
        onSubmit={async (message) => {
          const next = await withBusy(() => continueJob(job.job_id, { message }));
          onNewJob(next);
        }}
      />
    </section>
  );
}
