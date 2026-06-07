"use client";

import { ArrowUp, Loader2 } from "lucide-react";
import { useState } from "react";

interface TaskComposerProps {
  disabled?: boolean;
  placeholder?: string;
  onSubmit: (message: string) => Promise<void>;
}

export function TaskComposer({
  disabled = false,
  placeholder = "Continue this task — describe what to do next…",
  onSubmit,
}: TaskComposerProps) {
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event?: React.FormEvent) {
    event?.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || disabled || submitting) return;

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(trimmed);
      setMessage("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send");
    } finally {
      setSubmitting(false);
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  }

  return (
    <form
      onSubmit={(event) => void handleSubmit(event)}
      className="border-t border-white/[0.06] bg-[#0c0c12]/80 px-4 py-3 backdrop-blur-md"
    >
      <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-white/10 bg-black/40 p-2 shadow-inner focus-within:border-accent/40 focus-within:ring-1 focus-within:ring-accent/30">
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled || submitting}
          rows={2}
          placeholder={placeholder}
          className="max-h-40 min-h-[52px] flex-1 resize-none bg-transparent px-2 py-2 text-sm text-zinc-100 outline-none placeholder:text-zinc-600"
        />
        <button
          type="submit"
          disabled={disabled || submitting || !message.trim()}
          className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent text-white transition hover:bg-accent-glow disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Send follow-up"
        >
          {submitting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ArrowUp className="h-4 w-4" />
          )}
        </button>
      </div>
      <div className="mx-auto mt-2 flex max-w-3xl items-center justify-between px-1">
        <p className="text-[10px] text-zinc-600">
          Enter to send · Shift+Enter for newline
        </p>
        {error && <p className="text-[10px] text-red-400">{error}</p>}
      </div>
    </form>
  );
}
