export type JobStatus =
  | "QUEUED"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export type MessageRole = "user" | "assistant" | "system";

export interface Project {
  id: number;
  name: string;
  repo_url: string;
  settings: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface Job {
  job_id: string;
  project_id: number;
  status: JobStatus;
  level: string;
  preset: string;
  task: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  logs_path: string | null;
  error_message: string | null;
  parent_job_id?: string | null;
  thread_root_id?: string | null;
  log_tail?: string | null;
  can_auto_fix?: boolean;
}

export interface JobMessage {
  id: number;
  job_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
}

export interface HealthStatus {
  status: string;
  worker_running: boolean;
  queued_jobs: number;
  running_jobs: number;
}

export interface CreateProjectPayload {
  name: string;
  repo_url: string;
  settings?: Record<string, unknown>;
}

export interface TriggerJobPayload {
  task: string;
  level?: string;
  preset?: string;
}

export interface AgentPresetInfo {
  id: string;
  label: string;
  description: string;
  default_level: string;
  capabilities: string[];
}

export interface ContinueJobPayload {
  message: string;
}

export type TaskListFilter = "all" | "active" | "done";
