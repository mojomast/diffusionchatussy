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

/** All possible WebSocket message types from the backend */
export type WSMessage =
  | WSChatMessage
  | WSDiffusionStart
  | WSDiffusionStep
  | WSToneChange
  | WSPong;

export interface WSChatMessage {
  type: "chat";
  msg_id?: string;
  user: string;
  message: string;
  original?: string;
  timestamp: number;
  tone_name?: string;
  diffused?: boolean;
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
