// Type definitions that mirror the backend's Pydantic schemas in
// `backend/app/schemas.py`. Keeping them in sync by hand is fine at this
// scale; for a bigger project we'd auto-generate from the OpenAPI schema.
//
// These types are used everywhere — `api.ts` for response typing, the
// React pages for prop typing — so changing one means TypeScript will
// flag everything that needs to follow.

/** A single VibeRoom user as returned by the API. */
export type User = {
  id: string;
  name: string;
  vibe_text: string;
  interests: string[];
  // ISO 8601 timestamp string (the backend serialises datetimes this way).
  created_at: string;
};

/** Structured result of the LLM's vibe-analysis step. */
export type VibeAnalysis = {
  mood: string;
  energy_level: number; // 1–10, clamped server-side
  key_themes: string[];
  summary: string;
};

/** One suggested match plus the AI extras we render on the card. */
export type Match = {
  user: User;
  similarity_score: number; // 0..1 — multiply by 100 for the % badge
  vibe_analysis: VibeAnalysis | null;
  icebreakers: string[];
};

/** The full payload returned by POST /users and GET /users/:id/matches. */
export type AgentResult = {
  user: User;
  vibe_analysis: VibeAnalysis;
  matches: Match[];
};

/** Body the client sends to POST /users. */
export type CreateUserPayload = {
  name: string;
  vibe_text: string;
  interests: string[];
};
