"use client";

import {
  Ban,
  ListRestart,
  MessageSquarePlus,
  RotateCcw,
} from "lucide-react";
import { useState, type ReactNode } from "react";

import type { Job } from "@/lib/types";

interface TaskActionsBarProps {
  job: Job;
  busy?: boolean;
  onRestart: () => Promise<void>;
  onRequeue: () => Promise<void>;
  onCancel: () => Promise<void>;
}

function ActionButton({
  label,
  icon,
  onClick,
  disabled,
  variant = "default",
}: {
  label: string;
  icon: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  variant?: "default" | "danger";
}) {
  const base =
    "inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-40";
  const styles =
    variant === "danger"
      ? "border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20"
      : "border-white/10 bg-white/[0.03] text-zinc-300 hover:bg-white/[0.07]";

  return (
    <button type="button" onClick={onClick} disabled={disabled} className={`${base} ${styles}`} title={label}>
      {icon}
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

export function TaskActionsBar({
  job,
  busy = false,
  onRestart,
  onRequeue,
  onCancel,
}: TaskActionsBarProps) {
  const [actionError, setActionError] = useState<string | null>(null);
  const isActive = job.status === "QUEUED" || job.status === "RUNNING";
  const isTerminal =
    job.status === "COMPLETED" || job.status === "FAILED" || job.status === "CANCELLED";

  async function run(action: () => Promise<void>) {
    setActionError(null);
    try {
      await action();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Action failed");
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {isTerminal && (
        <>
          <ActionButton
            label="Restart"
            icon={<RotateCcw className="h-3.5 w-3.5" />}
            disabled={busy}
            onClick={() => void run(onRestart)}
          />
          <ActionButton
            label="Requeue"
            icon={<ListRestart className="h-3.5 w-3.5" />}
            disabled={busy}
            onClick={() => void run(onRequeue)}
          />
        </>
      )}
      {isActive && (
        <ActionButton
          label="Cancel"
          icon={<Ban className="h-3.5 w-3.5" />}
          disabled={busy}
          variant="danger"
          onClick={() => void run(onCancel)}
        />
      )}
      {job.parent_job_id && (
        <span className="inline-flex items-center gap-1 rounded-full border border-white/10 px-2 py-0.5 text-[10px] text-zinc-500">
          <MessageSquarePlus className="h-3 w-3" />
          Continuation
        </span>
      )}
      {actionError && <span className="text-xs text-red-400">{actionError}</span>}
    </div>
  );
}
