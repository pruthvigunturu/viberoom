export type User = {
  id: string;
  name: string;
  vibe_text: string;
  interests: string[];
  created_at: string;
};

export type VibeAnalysis = {
  mood: string;
  energy_level: number;
  key_themes: string[];
  summary: string;
};

export type Match = {
  user: User;
  similarity_score: number;
  vibe_analysis: VibeAnalysis | null;
  icebreakers: string[];
};

export type AgentResult = {
  user: User;
  vibe_analysis: VibeAnalysis;
  matches: Match[];
};

export type CreateUserPayload = {
  name: string;
  vibe_text: string;
  interests: string[];
};
