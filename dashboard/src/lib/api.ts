import { FALLBACK_MODELS, mapModelResponses, type ModelResponseDto } from "./models";
import type {
  AgentPresetInfo,
  ApiUsageStats,
  AutoFixJobPayload,
  ContinueJobPayload,
  CreateProjectPayload,
  CursorApiKeyStatus,
  HealthStatus,
  Job,
  JobMessage,
  ModelInfo,
  Project,
  SettingsStatus,
  TriggerTaskRequest,
} from "./types";

const SERVER_API_URL =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

/** Browser uses same-origin proxy; server-side calls hit the API directly. */
export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    return "/api-backend";
  }
  return SERVER_API_URL;
}

function getAuthHeaders(): Record<string, string> {
  const token =
    (typeof window !== "undefined"
      ? process.env.NEXT_PUBLIC_ORCHESTRATOR_API_TOKEN
      : process.env.ORCHESTRATOR_API_TOKEN) ?? "";
  if (!token) {
    return {};
  }
  return { Authorization: `Bearer ${token}` };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl = getApiBaseUrl();
  const target = `${apiUrl}${path}`;
  console.log("Fetching from:", target);

  const response = await fetch(target, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function getWebSocketUrl(jobId: string): string {
  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}/api-backend/ws/logs/${jobId}`;
  }
  const base = SERVER_API_URL.replace(/^http/, "ws");
  return `${base}/ws/logs/${jobId}`;
}

export async function fetchHealth(): Promise<HealthStatus> {
  return request<HealthStatus>("/health");
}

export async function fetchProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}

export async function createProject(payload: CreateProjectPayload): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deleteProject(id: number): Promise<void> {
  await request<void>(`/projects/${id}`, { method: "DELETE" });
}

export async function fetchPresets(): Promise<AgentPresetInfo[]> {
  return request<AgentPresetInfo[]>("/presets");
}

export async function fetchModels(): Promise<ModelInfo[]> {
  const apiUrl = getApiBaseUrl();
  const target = `${apiUrl}/models`;

  try {
    const response = await fetch(target, {
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
    });

    if (response.status === 404) {
      return FALLBACK_MODELS;
    }

    if (!response.ok) {
      const body = await response.text();
      throw new Error(body || `Request failed: ${response.status}`);
    }

    const data = (await response.json()) as ModelResponseDto[];
    const mapped = mapModelResponses(data);
    return mapped.length > 0 ? mapped : FALLBACK_MODELS;
  } catch {
    return FALLBACK_MODELS;
  }
}

export async function fetchJobs(params?: {
  project_id?: number;
  status?: string;
  limit?: number;
}): Promise<Job[]> {
  const search = new URLSearchParams();
  if (params?.project_id != null) search.set("project_id", String(params.project_id));
  if (params?.status) search.set("status", params.status);
  if (params?.limit != null) search.set("limit", String(params.limit));
  const query = search.toString();
  return request<Job[]>(`/jobs${query ? `?${query}` : ""}`);
}

export async function fetchJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${jobId}`);
}

export async function triggerJob(
  projectId: number,
  payload: TriggerTaskRequest,
): Promise<Job> {
  return request<Job>(`/projects/${projectId}/jobs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchJobMessages(jobId: string): Promise<JobMessage[]> {
  return request<JobMessage[]>(`/jobs/${jobId}/messages`);
}

export async function restartJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${jobId}/restart`, { method: "POST" });
}

export async function requeueJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${jobId}/requeue`, { method: "POST" });
}

export async function cancelJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${jobId}/cancel`, { method: "POST" });
}

export async function continueJob(jobId: string, payload: ContinueJobPayload): Promise<Job> {
  return request<Job>(`/jobs/${jobId}/continue`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function autoFixJob(
  jobId: string,
  payload?: AutoFixJobPayload,
): Promise<Job> {
  const init: RequestInit = { method: "POST" };
  if (payload) {
    init.body = JSON.stringify(payload);
  }
  return request<Job>(`/jobs/${jobId}/auto-fix`, init);
}

export async function fetchSettings(): Promise<SettingsStatus> {
  return request<SettingsStatus>("/settings");
}

export async function updateCursorApiKey(apiKey: string): Promise<CursorApiKeyStatus> {
  return request<CursorApiKeyStatus>("/settings/cursor-api-key", {
    method: "PUT",
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export async function clearCursorApiKey(): Promise<void> {
  await request<void>("/settings/cursor-api-key", { method: "DELETE" });
}

export async function fetchApiStats(): Promise<ApiUsageStats> {
  return request<ApiUsageStats>("/stats/api-usage");
}
