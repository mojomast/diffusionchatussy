// ---------------------------------------------------------------------------
// API client — all HTTP calls to the backend
// ---------------------------------------------------------------------------

const BASE = "/api";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// --- Status ---

import type {
  StatusResponse,
  ToneConfig,
  ModelConfig,
  ChatMessage,
  UserSession,
  StatsResponse,
  MyStatsResponse,
  ContextStats,
  PersonalizationResponse,
  PersonalizationAccess,
} from "./types";

const DEFAULT_TONE_PROMPT_PRESETS = [
  { id: "none", label: "No extra prompt", prompt: "" },
];

function normalizePreferences(preferences?: Partial<UserSession["preferences"]>) {
  const legacyTarget = preferences?.target_language ?? "English";
  return {
    translation_enabled: preferences?.translation_enabled ?? false,
    speaking_language: preferences?.speaking_language ?? legacyTarget,
    perceiving_language: preferences?.perceiving_language ?? legacyTarget,
    target_language: preferences?.perceiving_language ?? preferences?.target_language ?? "English",
    tone_enabled: preferences?.tone_enabled ?? true,
    tone_prompt_preset_id: preferences?.tone_prompt_preset_id ?? "none",
    tone_prompt: preferences?.tone_prompt ?? "",
  };
}

function normalizeAccess(access?: Partial<PersonalizationAccess>): PersonalizationAccess {
  return {
    available_languages: access?.available_languages?.length
      ? access.available_languages
      : ["English"],
    allow_user_tone_prompt_edit: access?.allow_user_tone_prompt_edit ?? true,
    tone_prompt_presets: access?.tone_prompt_presets?.length
      ? access.tone_prompt_presets
      : DEFAULT_TONE_PROMPT_PRESETS,
  };
}

function normalizeSession(session: UserSession): UserSession {
  return {
    ...session,
    preferences: normalizePreferences(session.preferences),
  };
}

function normalizeMyStats(stats: MyStatsResponse): MyStatsResponse {
  return {
    ...stats,
    preferences: normalizePreferences(stats.preferences),
  };
}

function normalizePersonalizationResponse(
  response: PersonalizationResponse
): PersonalizationResponse {
  return {
    preferences: normalizePreferences(response.preferences),
    access: normalizeAccess(response.access),
  };
}

export async function getStatus(): Promise<StatusResponse> {
  return request<StatusResponse>("/");
}

// --- Auth ---

export async function joinChat(
  username: string
): Promise<UserSession> {
  const res = await request<UserSession>("/auth/join", {
    method: "POST",
    body: JSON.stringify({ username }),
  });
  return normalizeSession(res);
}

export async function getSession(): Promise<UserSession> {
  return normalizeSession(await request<UserSession>("/auth/session"));
}

export async function adminLogin(
  password: string
): Promise<UserSession> {
  const res = await request<UserSession>("/auth/admin", {
    method: "POST",
    body: JSON.stringify({ password }),
  });
  return normalizeSession(res);
}

export async function getPreferences(): Promise<PersonalizationResponse> {
  return normalizePersonalizationResponse(
    await request<PersonalizationResponse>("/preferences")
  );
}

export async function updatePreferences(
  preferences: Partial<{
    translation_enabled: boolean;
    speaking_language: string;
    perceiving_language: string;
    target_language: string;
    tone_enabled: boolean;
    tone_prompt_preset_id: string;
    tone_prompt: string;
  }>
): Promise<PersonalizationResponse> {
  return normalizePersonalizationResponse(await request<PersonalizationResponse>("/preferences", {
    method: "POST",
    body: JSON.stringify(preferences),
  }));
}

// --- Chat ---

export async function sendMessage(
  user: string,
  message: string
): Promise<ChatMessage & { rewritten: string; original: string }> {
  return request("/message", {
    method: "POST",
    body: JSON.stringify({ user, message }),
  });
}

export async function getMessages(
  limit = 100
): Promise<Array<{ user: string; original: string; rewritten: string; timestamp: number; tone_name: string; token_estimate?: number; tone_applied?: boolean; translation_language?: string | null; source_language?: string | null }>> {
  return request(`/messages?limit=${limit}`);
}

// --- Stats ---

export async function getStats(): Promise<StatsResponse> {
  return request<StatsResponse>("/stats");
}

export async function getMyStats(): Promise<MyStatsResponse> {
  return normalizeMyStats(await request<MyStatsResponse>("/stats/me"));
}

// --- Admin: User Management ---

export async function getUsers(): Promise<{ users: UserSession[]; total: number }> {
  const res = await request<{ users: UserSession[]; total: number }>("/admin/users", {
    method: "POST",
  });
  return {
    ...res,
    users: (res.users ?? []).map(normalizeSession),
  };
}

export async function getPersonalizationAccess(): Promise<PersonalizationAccess> {
  return normalizeAccess(await request<PersonalizationAccess>("/admin/personalization"));
}

export async function setPersonalizationAccess(
  access: Partial<{
    available_languages: string[];
    allow_user_tone_prompt_edit: boolean;
    tone_prompt_presets: Array<{ id: string; label: string; prompt: string }>;
  }>
): Promise<PersonalizationAccess> {
  return normalizeAccess(await request<PersonalizationAccess>("/admin/personalization", {
    method: "POST",
    body: JSON.stringify(access),
  }));
}

export async function setUserRole(
  userId: string,
  role: "user" | "admin"
): Promise<{ status: string }> {
  return request<{ status: string }>(`/admin/users/${userId}/role`, {
    method: "POST",
    body: JSON.stringify({ role }),
  });
}

export async function kickUser(
  userId: string
): Promise<{ status: string }> {
  return request<{ status: string }>(`/admin/users/${userId}/kick`, {
    method: "POST",
  });
}

// --- Admin: Context Management ---

export async function resetContext(): Promise<{ status: string }> {
  return request<{ status: string }>("/admin/context/reset", {
    method: "POST",
  });
}

export async function setContextSettings(
  settings: { max_messages?: number; max_tokens_per_user?: number }
): Promise<{ status: string }> {
  return request<{ status: string }>("/admin/context/settings", {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

export async function getContextStats(): Promise<ContextStats> {
  return request<ContextStats>("/admin/context");
}

// --- Tone ---

export async function getTone(): Promise<ToneConfig> {
  return request<ToneConfig>("/admin/tone");
}

export async function setTone(
  tone_name: string,
  description?: string,
  strength?: number
): Promise<ToneConfig> {
  return request<ToneConfig>("/admin/tone", {
    method: "POST",
    body: JSON.stringify({ tone_name, description, strength }),
  });
}

export async function getTonePresets(): Promise<Record<string, string>> {
  const res = await request<{ presets: Record<string, string> }>(
    "/admin/tone/presets"
  );
  return res.presets;
}

// --- Model ---

export async function getModel(): Promise<ModelConfig> {
  return request<ModelConfig>("/admin/model");
}

export async function setModel(
  config: Partial<{
    provider: string;
    model: string;
    api_key: string;
    base_url: string;
    diffusion: boolean;
    max_tokens: number;
    temperature: number;
    top_p: number;
    frequency_penalty: number;
    presence_penalty: number;
    timeout: number;
  }>
): Promise<ModelConfig> {
  return request<ModelConfig>("/admin/model", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export async function getProviderPresets(): Promise<
  Record<string, { base_url: string; default_model: string }>
> {
  const res = await request<{
    presets: Record<string, { base_url: string; default_model: string }>;
  }>("/admin/model/presets");
  return res.presets;
}

// --- OpenRouter Model Search ---

export interface OpenRouterModel {
  id: string;
  name: string;
  context_length: number;
  prompt_price: string;
  completion_price: string;
}

export async function searchOpenRouterModels(
  query: string = "",
  limit: number = 50
): Promise<{ models: OpenRouterModel[]; total: number }> {
  return request<{ models: OpenRouterModel[]; total: number }>(
    `/admin/openrouter/models?q=${encodeURIComponent(query)}&limit=${limit}`
  );
}

// --- OpenRouter Favorites ---

export interface OpenRouterFavorite {
  id: string;
  name: string;
  why: string;
}

export async function getOpenRouterFavorites(): Promise<{
  favorites: OpenRouterFavorite[];
}> {
  return request<{ favorites: OpenRouterFavorite[] }>(
    "/admin/openrouter/favorites"
  );
}
