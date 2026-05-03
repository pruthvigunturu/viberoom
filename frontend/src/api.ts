import type { AgentResult, CreateUserPayload, User, VibeAnalysis } from "./types";

const API_URL = (import.meta.env.VITE_API_URL as string) ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text || path}`);
  }
  return (await res.json()) as T;
}

export const api = {
  createUser: (data: CreateUserPayload) =>
    request<AgentResult>("/users", { method: "POST", body: JSON.stringify(data) }),
  listUsers: () => request<User[]>("/users"),
  getUser: (id: string) => request<User>(`/users/${id}`),
  getMatches: (id: string) => request<AgentResult>(`/users/${id}/matches`),
  getAgentTrace: (id: string) => request<VibeAnalysis>(`/users/${id}/agent-trace`),
};
