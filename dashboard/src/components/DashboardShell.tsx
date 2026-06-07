"use client";

import { Activity, Layers, Menu, Zap } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ApiConnectionBadge } from "@/components/ApiConnectionBadge";
import { MobileNav, type MobilePanel } from "@/components/MobileNav";
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

function sidePanelClass(visible: boolean): string {
  return visible
    ? "flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden lg:flex-none lg:shrink-0"
    : "hidden min-h-0 min-w-0 lg:flex lg:flex-none lg:shrink-0 lg:flex-col lg:overflow-hidden";
}

function workspacePanelClass(visible: boolean): string {
  return visible
    ? "workspace-main"
    : "hidden min-h-0 min-w-0 lg:flex lg:min-h-0 lg:min-w-0 lg:flex-1 lg:flex-col lg:overflow-hidden";
}

export function DashboardShell() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [taskFilter, setTaskFilter] = useState<TaskListFilter>("all");
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>("tasks");
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
    setMobilePanel("tasks");
  }, [selectedProjectId]);

  async function handleSelectJob(jobId: string) {
    setSelectedJobId(jobId);
    setMobilePanel("workspace");
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
    setMobilePanel("workspace");
  }

  async function handleCreateProject(name: string, repoUrl: string) {
    const project = await createProject({ name, repo_url: repoUrl });
    setProjects((prev) => [...prev, project]);
    setSelectedProjectId(project.id);
    setMobilePanel("tasks");
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

  async function handleTrigger(task: string, level: string, preset: string) {
    if (selectedProjectId == null) return;
    const job = await triggerJob(selectedProjectId, { task, level, preset });
    handleNewJob(job);
    await refresh();
  }

  return (
    <div className="app-shell">
      <aside
        className={`${sidePanelClass(mobilePanel === "projects")} glass-panel w-full border-r border-white/[0.06] lg:w-[min(100%,280px)] xl:w-[300px]`}
      >
        <div className="border-b border-white/[0.06] p-4 lg:border-none">
          <div className="mb-1 flex items-center gap-2">
            <Layers className="h-5 w-5 text-accent-glow" />
            <h1 className="text-base font-semibold tracking-tight">HyperOrchestrator</h1>
          </div>
          <p className="text-xs text-zinc-500">Multi-project control</p>
        </div>
        <div className="min-h-0 flex-1 overflow-hidden p-3 lg:p-4">
          <ProjectList
            projects={projects}
            selectedId={selectedProjectId}
            onSelect={(id) => {
              setSelectedProjectId(id);
              setMobilePanel("tasks");
            }}
            onCreate={handleCreateProject}
            onDelete={handleDeleteProject}
          />
        </div>
      </aside>

      {selectedProject ? (
        <>
          <div className={`${sidePanelClass(mobilePanel === "tasks")} lg:w-[min(100%,320px)]`}>
            <TaskListPanel
              jobs={jobs}
              filter={taskFilter}
              selectedJobId={selectedJobId}
              onFilterChange={setTaskFilter}
              onSelectJob={(jobId) => void handleSelectJob(jobId)}
            />
          </div>

          <main className={workspacePanelClass(mobilePanel === "workspace")}>
            <div className="top-bar shrink-0">
              <div className="flex min-w-0 items-center gap-2">
                <button
                  type="button"
                  className="icon-btn lg:hidden"
                  onClick={() => setMobilePanel("tasks")}
                  aria-label="Back to tasks"
                >
                  <Menu className="h-4 w-4" />
                </button>
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-semibold">{selectedProject.name}</h2>
                  <p className="truncate text-[11px] text-zinc-500">{selectedProject.repo_url}</p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {health && (
                  <div className="hidden items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] px-2.5 py-1.5 text-[10px] text-zinc-400 sm:flex">
                    <Activity className="h-3 w-3 text-emerald-400" />
                    <span>{health.running_jobs} run</span>
                    <span>{health.queued_jobs} queue</span>
                  </div>
                )}
                <motion.button
                  type="button"
                  whileTap={{ scale: 0.97 }}
                  onClick={() => setModalOpen(true)}
                  className="btn-primary"
                >
                  <Zap className="h-3.5 w-3.5" />
                  <span className="hidden xs:inline">New task</span>
                  <span className="xs:hidden">New</span>
                </motion.button>
              </div>
            </div>

            {error && (
              <div className="mx-3 mt-2 shrink-0 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300 lg:mx-5">
                {error}
              </div>
            )}

            <div className="workspace-main">
              {loading ? (
                <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">
                  Loading…
                </div>
              ) : (
                <TaskWorkspace
                  job={selectedJob}
                  onJobUpdated={handleJobUpdated}
                  onNewJob={handleNewJob}
                />
              )}
            </div>
          </main>
        </>
      ) : (
        <main className="flex flex-1 items-center justify-center px-6 text-center text-sm text-zinc-500">
          <div className="empty-state-card">
            <p>Select or create a project to begin.</p>
            <button
              type="button"
              className="btn-primary mt-4"
              onClick={() => setMobilePanel("projects")}
            >
              Open projects
            </button>
          </div>
        </main>
      )}

      <MobileNav
        active={mobilePanel}
        onChange={setMobilePanel}
        hasWorkspace={Boolean(selectedJobId)}
      />

      <ApiConnectionBadge compact />

      <TriggerTaskModal
        open={modalOpen}
        projectName={selectedProject?.name ?? "Project"}
        onClose={() => setModalOpen(false)}
        onSubmit={handleTrigger}
      />
    </div>
  );
}
