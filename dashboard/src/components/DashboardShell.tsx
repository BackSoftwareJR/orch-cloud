"use client";

import { Activity, Layers, Zap } from "lucide-react";

import { JobHistory } from "@/components/JobHistory";
import { JobQueue } from "@/components/JobQueue";
import { LiveTerminal } from "@/components/LiveTerminal";
import { ProjectList } from "@/components/ProjectList";
import { TriggerTaskModal } from "@/components/TriggerTaskModal";
import {
  createProject,
  deleteProject,
  fetchHealth,
  fetchJobs,
  fetchProjects,
  triggerJob,
} from "@/lib/api";
import type { HealthStatus, Job, Project } from "@/lib/types";
import { motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";

export function DashboardShell() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectedProject = projects.find((p) => p.id === selectedProjectId) ?? null;

  const refresh = useCallback(async () => {
    try {
      const [projectData, healthData] = await Promise.all([fetchProjects(), fetchHealth()]);
      setProjects(projectData);
      setHealth(healthData);

      if (projectData.length > 0 && selectedProjectId === null) {
        setSelectedProjectId(projectData[0].id);
      }

      const activeProjectId = selectedProjectId ?? projectData[0]?.id ?? null;
      if (activeProjectId != null) {
        const jobData = await fetchJobs({ project_id: activeProjectId, limit: 100 });
        setJobs(jobData);
      } else {
        setJobs([]);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, [selectedProjectId]);

  useEffect(() => {
    void refresh();
    const interval = setInterval(() => void refresh(), 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  async function handleCreateProject(name: string, repoUrl: string) {
    const project = await createProject({ name, repo_url: repoUrl });
    setProjects((prev) => [...prev, project]);
    setSelectedProjectId(project.id);
  }

  async function handleDeleteProject(id: number) {
    await deleteProject(id);
    setProjects((prev) => prev.filter((p) => p.id !== id));
    if (selectedProjectId === id) {
      setSelectedProjectId(null);
      setJobs([]);
    }
  }

  async function handleTrigger(task: string, level: string) {
    if (selectedProjectId == null) return;
    const job = await triggerJob(selectedProjectId, { task, level });
    setSelectedJobId(job.job_id);
    await refresh();
  }

  return (
    <div className="flex min-h-screen bg-[radial-gradient(ellipse_at_top,_rgba(99,102,241,0.12),_transparent_50%),#0a0a0f]">
      <aside className="glass-panel flex w-[320px] shrink-0 flex-col border-r border-white/[0.06] p-5">
        <div className="mb-8">
          <div className="mb-1 flex items-center gap-2">
            <Layers className="h-5 w-5 text-accent-glow" />
            <h1 className="text-base font-semibold tracking-tight">HyperOrchestrator</h1>
          </div>
          <p className="text-xs text-zinc-500">Multi-project orchestration platform</p>
        </div>
        <ProjectList
          projects={projects}
          selectedId={selectedProjectId}
          onSelect={setSelectedProjectId}
          onCreate={handleCreateProject}
          onDelete={handleDeleteProject}
        />
      </aside>

      <main className="flex min-w-0 flex-1 flex-col gap-5 p-6">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold tracking-tight">
              {selectedProject?.name ?? "Select a project"}
            </h2>
            <p className="text-sm text-zinc-500">
              {selectedProject?.repo_url ?? "Choose a repository from the sidebar"}
            </p>
          </div>

          <div className="flex items-center gap-3">
            {health && (
              <div className="glass-panel flex items-center gap-4 rounded-2xl px-4 py-2 text-xs">
                <span className="flex items-center gap-1.5 text-zinc-400">
                  <Activity className="h-3.5 w-3.5 text-emerald-400" />
                  Worker {health.worker_running ? "active" : "stopped"}
                </span>
                <span className="text-zinc-500">{health.queued_jobs} queued</span>
                <span className="text-zinc-500">{health.running_jobs} running</span>
              </div>
            )}
            <motion.button
              type="button"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              disabled={!selectedProject}
              onClick={() => setModalOpen(true)}
              className="flex items-center gap-2 rounded-2xl bg-accent px-4 py-2.5 text-sm font-medium text-white shadow-glow transition hover:bg-accent-glow disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Zap className="h-4 w-4" />
              New task
            </motion.button>
          </div>
        </header>

        {error && (
          <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">
            Loading dashboard…
          </div>
        ) : selectedProject ? (
          <div className="grid flex-1 grid-cols-1 gap-5 xl:grid-cols-2">
            <div className="flex flex-col gap-5">
              <JobQueue
                jobs={jobs}
                selectedJobId={selectedJobId}
                onSelectJob={setSelectedJobId}
              />
              <JobHistory
                jobs={jobs}
                selectedJobId={selectedJobId}
                onSelectJob={setSelectedJobId}
              />
            </div>
            <LiveTerminal jobId={selectedJobId} />
          </div>
        ) : (
          <div className="glass-panel flex flex-1 items-center justify-center rounded-3xl text-sm text-zinc-500">
            Add a project to start orchestrating tasks across repositories.
          </div>
        )}
      </main>

      <TriggerTaskModal
        open={modalOpen}
        projectName={selectedProject?.name ?? "Project"}
        onClose={() => setModalOpen(false)}
        onSubmit={handleTrigger}
      />
    </div>
  );
}
