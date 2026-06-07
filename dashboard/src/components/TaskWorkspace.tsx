"use client";

import { MessageSquare, Terminal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { LiveTerminal } from "@/components/LiveTerminal";
import { TaskActionsBar } from "@/components/TaskActionsBar";
import { TaskChat } from "@/components/TaskChat";
import { TaskComposer } from "@/components/TaskComposer";
import { useJobLiveFeed } from "@/hooks/useJobLiveFeed";
import {
  autoFixJob,
  cancelJob,
  continueJob,
  fetchJobMessages,
  requeueJob,
  restartJob,
} from "@/lib/api";
import { modelLabel, resolveJobModel } from "@/lib/models";
import { presetLabel } from "@/lib/presets";
import type { Job, JobMessage } from "@/lib/types";

interface TaskWorkspaceProps {
  job: Job | null;
  onJobUpdated: (job: Job) => void;
  onNewJob: (job: Job) => void;
}

type WorkspaceTab = "chat" | "terminal";

function statusBadgeClass(status: Job["status"]): string {
  switch (status) {
    case "RUNNING":
      return "status-running";
    case "QUEUED":
      return "status-queued";
    case "COMPLETED":
      return "status-completed";
    case "FAILED":
      return "status-failed";
    default:
      return "status-cancelled";
  }
}

function chatPanelClass(active: boolean): string {
  if (active) {
    return "flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden";
  }
  return "hidden min-h-0 min-w-0 lg:flex lg:min-h-0 lg:flex-1 lg:flex-col lg:overflow-hidden";
}

function terminalPanelClass(active: boolean): string {
  const shared =
    "min-h-0 min-w-0 flex-col overflow-hidden border-t border-white/[0.06] p-2 lg:max-h-[40vh] lg:min-h-[180px] lg:flex-none lg:p-3";
  if (active) {
    return `flex flex-1 ${shared}`;
  }
  return `hidden lg:flex ${shared}`;
}

export function TaskWorkspace({ job, onJobUpdated, onNewJob }: TaskWorkspaceProps) {
  const [messages, setMessages] = useState<JobMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [mobileTab, setMobileTab] = useState<WorkspaceTab>("chat");

  const isActive = job?.status === "RUNNING" || job?.status === "QUEUED";
  const { feed, lines, connected, error } = useJobLiveFeed({
    jobId: job?.job_id ?? null,
    messages,
    streamEnabled: isActive || Boolean(job),
  });

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
    setMobileTab("chat");
  }, [job, loadMessages]);

  useEffect(() => {
    if (!job || job.status !== "RUNNING") return;
    const interval = setInterval(() => void loadMessages(job.job_id), 3000);
    return () => clearInterval(interval);
  }, [job, loadMessages]);

  if (!job) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-hidden px-6 py-12 text-center">
        <div className="empty-state-card">
          <MessageSquare className="mx-auto mb-3 h-8 w-8 text-accent-glow/60" />
          <p className="text-sm font-medium text-zinc-300">Open a task to start</p>
          <p className="mt-2 max-w-sm text-xs leading-relaxed text-zinc-500">
            Live orchestrator updates stream into the chat. Full raw logs stay in the terminal tab.
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

  const chatVisible = mobileTab === "chat";
  const terminalVisible = mobileTab === "terminal";

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <header className="shrink-0 border-b border-white/[0.06] px-4 py-3 lg:px-5 lg:py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className={`status-badge ${statusBadgeClass(job.status)}`}>{job.status}</span>
              <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wider text-zinc-400">
                {job.level}
              </span>
              <span className="rounded-full bg-accent/10 px-2 py-0.5 text-[10px] uppercase tracking-wider text-accent-glow">
                {presetLabel(job.preset)}
              </span>
              <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] tracking-wide text-zinc-400">
                {modelLabel(resolveJobModel(job))}
              </span>
              <span className="font-mono text-[10px] text-zinc-600">{job.job_id.slice(0, 8)}</span>
            </div>
            <p className="line-clamp-3 text-sm leading-snug text-zinc-300 lg:line-clamp-2">
              {job.task.split("\n")[0]}
            </p>
            {job.error_message && (
              <p className="mt-2 text-xs leading-relaxed text-red-400">{job.error_message}</p>
            )}
          </div>
          <TaskActionsBar
            job={job}
            busy={actionBusy}
            onAutoFix={async () => {
              const next = await withBusy(() =>
                autoFixJob(job.job_id, { model: resolveJobModel(job) }),
              );
              onNewJob({ ...next, model: next.model ?? resolveJobModel(job) });
            }}
            onRestart={async () => {
              const activeModel = resolveJobModel(job);
              const next = await withBusy(() => restartJob(job.job_id));
              onNewJob({ ...next, model: next.model ?? activeModel });
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

        <div className="mt-3 flex gap-1 rounded-xl bg-black/40 p-1 lg:hidden">
          <button
            type="button"
            onClick={() => setMobileTab("chat")}
            className={`workspace-tab ${chatVisible ? "workspace-tab-active" : ""}`}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            Chat
          </button>
          <button
            type="button"
            onClick={() => setMobileTab("terminal")}
            className={`workspace-tab ${terminalVisible ? "workspace-tab-active" : ""}`}
          >
            <Terminal className="h-3.5 w-3.5" />
            Terminal
          </button>
        </div>
      </header>

      {/* Content: chat fills remaining space; terminal gets capped height on desktop */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className={chatPanelClass(chatVisible)}>
          <TaskChat
            items={feed}
            loading={loadingMessages}
            streaming={isActive}
            connected={connected}
          />
        </div>

        <div className={terminalPanelClass(terminalVisible)}>
          <LiveTerminal
            jobId={job.job_id}
            title="Raw terminal"
            lines={lines}
            connected={connected}
            error={error}
          />
        </div>
      </div>

      <div className="shrink-0">
        <TaskComposer
          disabled={!canContinue || actionBusy}
          placeholder={
            canContinue
              ? "Continue this task — describe what to do next…"
              : job.status === "RUNNING"
                ? "Agent is running… follow-up available when done"
                : "Queued — waiting for worker"
          }
          onSubmit={async (message) => {
            const activeModel = resolveJobModel(job);
            const next = await withBusy(() =>
              continueJob(job.job_id, { message, model: activeModel }),
            );
            onNewJob({ ...next, model: next.model ?? activeModel });
          }}
        />
      </div>
    </section>
  );
}
