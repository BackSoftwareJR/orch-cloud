"use client";

import { motion } from "framer-motion";
import { FolderGit2, Trash2 } from "lucide-react";

import type { Project } from "@/lib/types";

interface ProjectCardProps {
  project: Project;
  selected: boolean;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
}

export function ProjectCard({ project, selected, onSelect, onDelete }: ProjectCardProps) {
  return (
    <motion.button
      type="button"
      layout
      onClick={() => onSelect(project.id)}
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      className={`group w-full rounded-2xl p-4 text-left transition-colors ${
        selected
          ? "glass-panel border-accent/40 shadow-glow"
          : "border border-transparent bg-white/[0.03] hover:bg-white/[0.06]"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-center gap-2">
            <FolderGit2 className="h-4 w-4 shrink-0 text-accent-glow" />
            <span className="truncate font-medium tracking-tight">{project.name}</span>
          </div>
          <p className="truncate text-xs text-zinc-500">{project.repo_url}</p>
        </div>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onDelete(project.id);
          }}
          className="rounded-lg p-1.5 text-zinc-500 opacity-0 transition hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100"
          aria-label={`Delete ${project.name}`}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </motion.button>
  );
}
