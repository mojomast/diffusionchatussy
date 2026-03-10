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
} from "./types";

export async function getStatus(): Promise<StatusResponse> {
  return request<StatusResponse>("/");
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
): Promise<Array<{ user: string; original: string; rewritten: string; timestamp: number; tone_name: string }>> {
  return request(`/messages?limit=${limit}`);
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
