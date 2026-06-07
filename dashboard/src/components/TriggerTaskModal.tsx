"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Bug, Code2, Palette, Rocket, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchPresets } from "@/lib/api";
import type { AgentPresetInfo } from "@/lib/types";

interface TriggerTaskModalProps {
  open: boolean;
  projectName: string;
  onClose: () => void;
  onSubmit: (task: string, level: string, preset: string) => Promise<void>;
}

const LEVELS = [
  { value: "fast", label: "Fast", description: "Minimal fix, immediate push" },
  { value: "medium", label: "Medium", description: "Tests + auto-debug loop" },
  { value: "pro", label: "Pro", description: "AI-decomposed multi-step plan" },
];

const PRESET_ICONS: Record<string, typeof Palette> = {
  general: Sparkles,
  ux: Palette,
  backend: Code2,
  bugfix: Bug,
};

const FALLBACK_PRESETS: AgentPresetInfo[] = [
  {
    id: "general",
    label: "General",
    description: "Balanced full-stack engineer",
    default_level: "medium",
    capabilities: [],
  },
  {
    id: "ux",
    label: "UX / UI",
    description: "Expert designer for modern interfaces",
    default_level: "medium",
    capabilities: [],
  },
  {
    id: "backend",
    label: "Backend",
    description: "API, data layer, server logic",
    default_level: "medium",
    capabilities: [],
  },
  {
    id: "bugfix",
    label: "Bug Fix",
    description: "Root-cause analysis, minimal diff",
    default_level: "fast",
    capabilities: [],
  },
];

export function TriggerTaskModal({
  open,
  projectName,
  onClose,
  onSubmit,
}: TriggerTaskModalProps) {
  const [task, setTask] = useState("");
  const [level, setLevel] = useState("medium");
  const [preset, setPreset] = useState("general");
  const [presets, setPresets] = useState<AgentPresetInfo[]>(FALLBACK_PRESETS);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    void fetchPresets()
      .then(setPresets)
      .catch(() => setPresets(FALLBACK_PRESETS));
  }, [open]);

  function selectPreset(next: AgentPresetInfo) {
    setPreset(next.id);
    setLevel(next.default_level);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(task.trim(), level, preset);
      setTask("");
      setLevel("medium");
      setPreset("general");
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
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 backdrop-blur-sm sm:items-center sm:p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 24 }}
            onClick={(e) => e.stopPropagation()}
            className="glass-panel max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-t-3xl p-6 shadow-glow sm:rounded-3xl"
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
                <label className="mb-2 block text-xs text-zinc-400">Agent specialist</label>
                <div className="grid grid-cols-2 gap-2">
                  {presets.map((item) => {
                    const Icon = PRESET_ICONS[item.id] ?? Sparkles;
                    const active = preset === item.id;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => selectPreset(item)}
                        className={`rounded-2xl border px-3 py-3 text-left transition ${
                          active
                            ? "border-accent/50 bg-accent/15"
                            : "border-white/10 bg-white/[0.02] hover:bg-white/[0.05]"
                        }`}
                      >
                        <div className="mb-1 flex items-center gap-1.5">
                          <Icon className="h-3.5 w-3.5 text-accent-glow" />
                          <span className="text-sm font-medium">{item.label}</span>
                        </div>
                        <p className="text-[10px] leading-snug text-zinc-500">{item.description}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className="mb-2 block text-xs text-zinc-400">Task description</label>
                <textarea
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  required
                  rows={4}
                  className="w-full resize-none rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm outline-none ring-accent/40 focus:ring-2"
                  placeholder="Redesign the news page as a modern editorial board…"
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
                      className={`rounded-2xl border px-2 py-2.5 text-left transition sm:px-3 sm:py-3 ${
                        level === item.value
                          ? "border-accent/50 bg-accent/15"
                          : "border-white/10 bg-white/[0.02] hover:bg-white/[0.05]"
                      }`}
                    >
                      <div className="text-xs font-medium sm:text-sm">{item.label}</div>
                      <div className="mt-1 hidden text-[10px] leading-snug text-zinc-500 sm:block">
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
