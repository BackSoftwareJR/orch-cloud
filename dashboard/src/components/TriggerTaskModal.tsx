"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Rocket, X } from "lucide-react";
import { useState } from "react";

interface TriggerTaskModalProps {
  open: boolean;
  projectName: string;
  onClose: () => void;
  onSubmit: (task: string, level: string) => Promise<void>;
}

const LEVELS = [
  { value: "fast", label: "Fast", description: "Minimal fix, immediate push" },
  { value: "medium", label: "Medium", description: "Tests + auto-debug loop" },
  { value: "pro", label: "Pro", description: "AI-decomposed multi-step plan" },
];

export function TriggerTaskModal({
  open,
  projectName,
  onClose,
  onSubmit,
}: TriggerTaskModalProps) {
  const [task, setTask] = useState("");
  const [level, setLevel] = useState("medium");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(task.trim(), level);
      setTask("");
      setLevel("medium");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to trigger task");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            onClick={(e) => e.stopPropagation()}
            className="glass-panel w-full max-w-lg rounded-3xl p-6 shadow-glow"
          >
            <div className="mb-5 flex items-start justify-between">
              <div>
                <div className="mb-1 flex items-center gap-2 text-accent-glow">
                  <Rocket className="h-4 w-4" />
                  <span className="text-xs font-medium uppercase tracking-wider">
                    Trigger task
                  </span>
                </div>
                <h2 className="text-lg font-semibold tracking-tight">{projectName}</h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-xl p-2 text-zinc-500 transition hover:bg-white/5 hover:text-zinc-300"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="mb-2 block text-xs text-zinc-400">Task description</label>
                <textarea
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  required
                  rows={4}
                  className="w-full resize-none rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm outline-none ring-accent/40 focus:ring-2"
                  placeholder="Fix N+1 query on users index…"
                />
              </div>

              <div>
                <label className="mb-2 block text-xs text-zinc-400">Execution level</label>
                <div className="grid grid-cols-3 gap-2">
                  {LEVELS.map((item) => (
                    <button
                      key={item.value}
                      type="button"
                      onClick={() => setLevel(item.value)}
                      className={`rounded-2xl border px-3 py-3 text-left transition ${
                        level === item.value
                          ? "border-accent/50 bg-accent/15"
                          : "border-white/10 bg-white/[0.02] hover:bg-white/[0.05]"
                      }`}
                    >
                      <div className="text-sm font-medium">{item.label}</div>
                      <div className="mt-1 text-[10px] leading-snug text-zinc-500">
                        {item.description}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {error && <p className="text-xs text-red-400">{error}</p>}

              <button
                type="submit"
                disabled={submitting}
                className="flex w-full items-center justify-center gap-2 rounded-2xl bg-accent px-4 py-3 text-sm font-medium text-white transition hover:bg-accent-glow disabled:opacity-50"
              >
                <Rocket className="h-4 w-4" />
                {submitting ? "Queuing…" : "Queue orchestration"}
              </button>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
