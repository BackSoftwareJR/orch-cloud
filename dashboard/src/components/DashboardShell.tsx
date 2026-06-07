"use client";

import { Activity, Layers, Zap } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ProjectList } from "@/components/ProjectList";
import { TaskListPanel } from "@/components/TaskListPanel";
import { TaskWorkspace } from "@/components/TaskWorkspace";
import { TriggerTaskModal } from "@/components/TriggerTaskModal";
import {
  createProject,
  deleteProject,
  fetchHealth,
  fetchJob,
  fetchJobs,
  fetchProjects,
  getApiBaseUrl,
  triggerJob,
} from "@/lib/api";
import type { HealthStatus, Job, Project, TaskListFilter } from "@/lib/types";
import { motion } from "framer-motion";

export function DashboardShell() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [taskFilter, setTaskFilter] = useState<TaskListFilter>("all");
  const [modalOpen, setModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;

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

        if (selectedJobId) {
          const stillExists = jobData.some((job) => job.job_id === selectedJobId);
          if (stillExists) {
            const detail = await fetchJob(selectedJobId);
            setSelectedJob(detail);
          } else {
            setSelectedJobId(null);
            setSelectedJob(null);
          }
        }
      } else {
        setJobs([]);
      }
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load dashboard";
      setError(`${message} → ${getApiBaseUrl()}`);
    } finally {
      setLoading(false);
    }
  }, [selectedProjectId, selectedJobId]);

  useEffect(() => {
    void refresh();
    const interval = setInterval(() => void refresh(), 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  useEffect(() => {
    setSelectedJobId(null);
    setSelectedJob(null);
  }, [selectedProjectId]);

  async function handleSelectJob(jobId: string) {
    setSelectedJobId(jobId);
    try {
      const detail = await fetchJob(jobId);
      setSelectedJob(detail);
    } catch {
      setSelectedJob(jobs.find((job) => job.job_id === jobId) ?? null);
    }
  }

  function handleJobUpdated(job: Job) {
    setJobs((prev) => prev.map((item) => (item.job_id === job.job_id ? job : item)));
    if (selectedJobId === job.job_id) {
      setSelectedJob(job);
    }
  }

  function handleNewJob(job: Job) {
    setJobs((prev) => [job, ...prev.filter((item) => item.job_id !== job.job_id)]);
    setSelectedJobId(job.job_id);
    setSelectedJob(job);
    setTaskFilter("active");
  }

  async function handleCreateProject(name: string, repoUrl: string) {
    const project = await createProject({ name, repo_url: repoUrl });
    setProjects((prev) => [...prev, project]);
    setSelectedProjectId(project.id);
  }

  async function handleDeleteProject(id: number) {
    await deleteProject(id);
    setProjects((prev) => prev.filter((project) => project.id !== id));
    if (selectedProjectId === id) {
      setSelectedProjectId(null);
      setJobs([]);
      setSelectedJobId(null);
      setSelectedJob(null);
    }
  }

  async function handleTrigger(task: string, level: string) {
    if (selectedProjectId == null) return;
    const job = await triggerJob(selectedProjectId, { task, level });
    handleNewJob(job);
    await refresh();
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[radial-gradient(ellipse_at_top,_rgba(99,102,241,0.12),_transparent_50%),#0a0a0f]">
      <aside className="glass-panel flex w-[260px] shrink-0 flex-col border-r border-white/[0.06] p-4">
        <div className="mb-6">
          <div className="mb-1 flex items-center gap-2">
            <Layers className="h-5 w-5 text-accent-glow" />
            <h1 className="text-base font-semibold tracking-tight">HyperOrchestrator</h1>
          </div>
          <p className="text-xs text-zinc-500">Task control center</p>
        </div>
        <ProjectList
          projects={projects}
          selectedId={selectedProjectId}
          onSelect={setSelectedProjectId}
          onCreate={handleCreateProject}
          onDelete={handleDeleteProject}
        />
      </aside>

      {selectedProject ? (
        <>
          <TaskListPanel
            jobs={jobs}
            filter={taskFilter}
            selectedJobId={selectedJobId}
            onFilterChange={setTaskFilter}
            onSelectJob={(jobId) => void handleSelectJob(jobId)}
          />
          <main className="flex min-w-0 flex-1 flex-col">
            <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-3">
              <div className="min-w-0">
                <h2 className="truncate text-sm font-semibold">{selectedProject.name}</h2>
                <p className="truncate text-xs text-zinc-500">{selectedProject.repo_url}</p>
              </div>
              <div className="flex items-center gap-3">
                {health && (
                  <div className="hidden items-center gap-3 rounded-xl border border-white/10 bg-white/[0.02] px-3 py-1.5 text-[10px] text-zinc-400 sm:flex">
                    <span className="inline-flex items-center gap-1">
                      <Activity className="h-3 w-3 text-emerald-400" />
                      Worker {health.worker_running ? "on" : "off"}
                    </span>
                    <span>{health.queued_jobs} queued</span>
                    <span>{health.running_jobs} running</span>
                  </div>
                )}
                <motion.button
                  type="button"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => setModalOpen(true)}
                  className="inline-flex items-center gap-2 rounded-xl bg-accent px-3 py-2 text-xs font-medium text-white shadow-glow hover:bg-accent-glow"
                >
                  <Zap className="h-3.5 w-3.5" />
                  New task
                </motion.button>
              </div>
            </div>

            {error && (
              <div className="mx-5 mt-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2 text-xs text-red-300">
                {error}
              </div>
            )}

            {loading ? (
              <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">
                Loading workspace…
              </div>
            ) : (
              <TaskWorkspace
                job={selectedJob}
                onJobUpdated={handleJobUpdated}
                onNewJob={handleNewJob}
              />
            )}
          </main>
        </>
      ) : (
        <main className="flex flex-1 items-center justify-center text-sm text-zinc-500">
          Add a project to start orchestrating tasks.
        </main>
      )}

      <TriggerTaskModal
        open={modalOpen}
        projectName={selectedProject?.name ?? "Project"}
        onClose={() => setModalOpen(false)}
        onSubmit={handleTrigger}
      />
    </div>
  );
}
