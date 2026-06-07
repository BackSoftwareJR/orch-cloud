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

export type ModelProvider = "cursor" | "anthropic" | "openai";
export type ModelBilling = "included" | "api_credits";

export interface ModelInfo {
  id: string;
  label: string;
  description: string;
  provider: ModelProvider;
  billing: ModelBilling;
  presets: string[];
  default_for?: string[];
}

export interface Job {
  job_id: string;
  project_id: number;
  status: JobStatus;
  level: string;
  preset: string;
  model?: string | null;
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
  cursor_api_key?: CursorApiKeyStatus | null;
}

export interface CursorApiKeyStatus {
  configured: boolean;
  masked_preview: string | null;
  updated_at: string | null;
  source_path?: string | null;
}

export interface SettingsStatus {
  cursor_api_key: CursorApiKeyStatus;
}

export interface ApiUsageRecentCall {
  id: number;
  endpoint: string;
  method: string;
  source: string;
  status_code: number;
  project_id: number | null;
  created_at: string;
}

export interface ApiUsageStats {
  total: number;
  today: number;
  this_week: number;
  by_source: Record<string, number>;
  by_endpoint: Record<string, number>;
  recent: ApiUsageRecentCall[];
}

export interface CreateProjectPayload {
  name: string;
  repo_url: string;
  settings?: Record<string, unknown>;
}

export interface TriggerTaskRequest {
  task: string;
  level?: string;
  preset?: string;
  model?: string;
}

/** @deprecated Use TriggerTaskRequest */
export type TriggerJobPayload = TriggerTaskRequest;

export interface AgentPresetInfo {
  id: string;
  label: string;
  description: string;
  default_level: string;
  default_model?: string;
  capabilities: string[];
}

export interface ContinueJobPayload {
  message: string;
  model?: string;
}

export interface AutoFixJobPayload {
  model?: string;
}

export type TaskListFilter = "all" | "active" | "done";
