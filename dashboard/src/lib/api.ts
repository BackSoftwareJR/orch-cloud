import type {
  CreateProjectPayload,
  HealthStatus,
  Job,
  Project,
  TriggerJobPayload,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
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

export function getApiBaseUrl(): string {
  return API_URL;
}

export function getWebSocketUrl(jobId: string): string {
  const base = API_URL.replace(/^http/, "ws");
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
  payload: TriggerJobPayload,
): Promise<Job> {
  return request<Job>(`/projects/${projectId}/jobs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
