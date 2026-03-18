// ---------------------------------------------------------------------------
// Shared types matching the backend API
// ---------------------------------------------------------------------------

export interface ChatMessage {
  user: string;
  message: string;        // rewritten text (final)
  original?: string;      // raw text
  timestamp: number;
  tone_name: string;
  msg_id?: string;
  diffused?: boolean;     // true if this message went through real diffusion
  rewrite_status?: "ok" | "passthrough" | "no_key" | "error";
  token_estimate?: number; // estimated token count for this message
  tone_applied?: boolean;
  translation_language?: string | null;
  source_language?: string | null;
}

export interface ToneConfig {
  tone_name: string;
  description: string;
  strength: number;
}

export interface ModelConfig {
  provider: string;
  model: string;
  has_api_key: boolean;
  base_url: string;
  diffusion: boolean;
  diffusion_available: boolean;
  max_tokens: number;
  temperature: number;
  top_p: number;
  frequency_penalty: number;
  presence_penalty: number;
  timeout: number;
}

export interface StatusResponse {
  status: string;
  connected_clients: number;
  message_count: number;
  tone: ToneConfig;
  model: ModelConfig;
}

// ---------------------------------------------------------------------------
// User session & stats types (backend auth system)
// ---------------------------------------------------------------------------

export interface UserSession {
  user_id: string;
  username: string;
  role: "user" | "admin";
  joined_at: number;
  last_active: number;
  total_messages: number;
  total_tokens_used: number;
  preferences: UserPreferences;
}

export interface UserPreferences {
  translation_enabled: boolean;
  speaking_language: string;
  perceiving_language: string;
  target_language: string;
  tone_enabled: boolean;
  tone_prompt_preset_id: string;
  tone_prompt: string;
}

export interface TonePromptPreset {
  id: string;
  label: string;
  prompt: string;
}

export interface PersonalizationAccess {
  available_languages: string[];
  allow_user_tone_prompt_edit: boolean;
  tone_prompt_presets: TonePromptPreset[];
}

export interface PersonalizationResponse {
  preferences: UserPreferences;
  access: PersonalizationAccess;
}

export interface StatsResponse {
  total_messages: number;
  total_tokens: number;
  active_users: number;
  users: UserSession[];
}

export interface MyStatsResponse {
  user_id: string;
  username: string;
  role: "user" | "admin";
  total_messages: number;
  total_tokens_used: number;
  joined_at: number;
  last_active: number;
  preferences: UserPreferences;
}

export interface ContextStats {
  message_count: number;
  total_tokens: number;
  max_messages: number;
  max_tokens_per_user: number;
}

// ---------------------------------------------------------------------------
// System message type for UI-only display (joins, leaves, resets)
// ---------------------------------------------------------------------------

export interface SystemMessage {
  type: "system";
  text: string;
  timestamp: number;
}

// A display item is either a real chat message or a system notification
export type DisplayMessage = (ChatMessage & { kind: "chat" }) | (SystemMessage & { kind: "system" });

// ---------------------------------------------------------------------------
// WebSocket message types
// ---------------------------------------------------------------------------

/** All possible WebSocket message types from the backend */
export type WSMessage =
  | WSChatMessage
  | WSDiffusionStart
  | WSDiffusionStep
  | WSToneChange
  | WSPong
  | WSContextReset
  | WSUserJoined
  | WSUserLeft
  | WSStatsUpdate;

export interface WSChatMessage {
  type: "chat";
  msg_id?: string;
  user: string;
  message: string;
  original?: string;
  timestamp: number;
  tone_name?: string;
  diffused?: boolean;
  rewrite_status?: "ok" | "passthrough" | "no_key" | "error";
  token_estimate?: number;
  tone_applied?: boolean;
  translation_language?: string | null;
  source_language?: string | null;
}

export interface WSDiffusionStart {
  type: "diffusion_start";
  msg_id: string;
  user: string;
  original: string;
  timestamp: number;
  tone_name?: string;
}

export interface WSDiffusionStep {
  type: "diffusion_step";
  msg_id: string;
  user: string;
  content: string;       // Current denoised state (full replacement, not incremental)
  step: number;
  timestamp: number;
}

export interface WSToneChange {
  type: "tone_change";
  tone_name?: string;
  description?: string;
  strength?: number;
}

export interface WSPong {
  type: "pong";
}

export interface WSContextReset {
  type: "context_reset";
}

export interface WSUserJoined {
  type: "user_joined";
  username: string;
  user_count: number;
}

export interface WSUserLeft {
  type: "user_left";
  username: string;
  user_count: number;
}

export interface WSStatsUpdate {
  type: "stats_update";
  total_messages: number;
  total_tokens: number;
  active_users: number;
}

/**
 * A message that is currently being diffused in the UI.
 * Tracks the evolving content through denoising steps.
 */
export interface DiffusingMessage {
  msg_id: string;
  user: string;
  original: string;
  currentContent: string;  // Latest denoised state
  step: number;
  timestamp: number;
  tone_name: string;
}
