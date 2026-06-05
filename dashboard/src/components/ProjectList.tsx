"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Plus } from "lucide-react";
import { useState } from "react";

import { ProjectCard } from "@/components/ProjectCard";
import type { Project } from "@/lib/types";

interface ProjectListProps {
  projects: Project[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onCreate: (name: string, repoUrl: string) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
}

export function ProjectList({
  projects,
  selectedId,
  onSelect,
  onCreate,
  onDelete,
}: ProjectListProps) {
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onCreate(name.trim(), repoUrl.trim());
      setName("");
      setRepoUrl("");
      setShowForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-zinc-200">Projects</h2>
          <p className="text-xs text-zinc-500">{projects.length} repositories</p>
        </div>
        <motion.button
          type="button"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => setShowForm((value) => !value)}
          className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/20 text-accent-glow transition hover:bg-accent/30"
        >
          <Plus className="h-4 w-4" />
        </motion.button>
      </div>

      <AnimatePresence>
        {showForm && (
          <motion.form
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            onSubmit={handleSubmit}
            className="glass-panel overflow-hidden rounded-2xl p-4"
          >
            <label className="mb-2 block text-xs text-zinc-400">Project name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="mb-3 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none ring-accent/40 focus:ring-2"
              placeholder="My App"
            />
            <label className="mb-2 block text-xs text-zinc-400">Repository URL</label>
            <input
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              required
              className="mb-3 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-sm outline-none ring-accent/40 focus:ring-2"
              placeholder="https://github.com/org/repo.git"
            />
            {error && <p className="mb-2 text-xs text-red-400">{error}</p>}
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-xl bg-accent px-3 py-2 text-sm font-medium text-white transition hover:bg-accent-glow disabled:opacity-50"
            >
              {submitting ? "Creating…" : "Add project"}
            </button>
          </motion.form>
        )}
      </AnimatePresence>

      <div className="scrollbar-thin flex-1 space-y-2 overflow-y-auto pr-1">
        {projects.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-white/10 p-6 text-center text-sm text-zinc-500">
            No projects yet. Add a repository to begin orchestrating tasks.
          </p>
        ) : (
          projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              selected={selectedId === project.id}
              onSelect={onSelect}
              onDelete={(id) => {
                void onDelete(id);
              }}
            />
          ))
        )}
      </div>
    </div>
  );
}
