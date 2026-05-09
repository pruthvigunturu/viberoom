// Thin wrapper around `fetch` that gives the rest of the app a typed API
// surface. Every call goes through `request<T>` so error handling, JSON
// parsing, and the base URL live in exactly one place.
import type { AgentResult, CreateUserPayload, User, VibeAnalysis } from "./types";

// `import.meta.env.VITE_API_URL` is set at build time by Vite (see
// `vercel.json` / `.env`). In local dev we fall back to the FastAPI port.
// Any env var Vite exposes to the browser must start with `VITE_`.
const API_URL = (import.meta.env.VITE_API_URL as string) ?? "http://localhost:8000";

/**
 * Generic JSON HTTP helper.
 *
 * - Adds the `Content-Type: application/json` header by default.
 * - Throws a useful Error on non-2xx so callers can rely on the happy path.
 * - The `<T>` type parameter lets each named API method declare its own
 *   response shape (see `api.createUser` below).
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    // Best-effort: try to surface the server's error body in the message.
    // `.catch(() => "")` swallows the (rare) case where reading the body fails.
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text || path}`);
  }
  return (await res.json()) as T;
}

/**
 * Public API surface. Each method maps 1:1 to a FastAPI route and is fully
 * typed so the React pages get autocomplete + compile-time checks.
 */
export const api = {
  createUser: (data: CreateUserPayload) =>
    request<AgentResult>("/users", { method: "POST", body: JSON.stringify(data) }),
  listUsers: () => request<User[]>("/users"),
  getUser: (id: string) => request<User>(`/users/${id}`),
  getMatches: (id: string) => request<AgentResult>(`/users/${id}/matches`),
  getAgentTrace: (id: string) => request<VibeAnalysis>(`/users/${id}/agent-trace`),
};
