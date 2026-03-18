"""
Tone-Field Chat — Request / Response Models

Pydantic schemas for all API endpoints including auth, stats, and admin.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class SendMessageRequest(BaseModel):
    user: str = Field(..., min_length=1, max_length=50)
    message: str = Field(..., min_length=1, max_length=2000)


class ChatMessage(BaseModel):
    user: str
    original: str
    rewritten: str
    timestamp: float
    tone_name: str
    tone_strength: int
    tokens_in: int = 0
    tokens_out: int = 0
    tone_applied: bool = True
    translation_language: Optional[str] = None
    source_language: Optional[str] = None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class JoinRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)


class AdminAuthRequest(BaseModel):
    password: str = Field(..., min_length=1)


class SessionResponse(BaseModel):
    user_id: str
    username: str
    role: str
    joined_at: float
    last_active: float
    total_messages: int
    total_tokens_used: int
    preferences: "UserPreferences"


# ---------------------------------------------------------------------------
# Personalization
# ---------------------------------------------------------------------------

class UserPreferences(BaseModel):
    translation_enabled: bool
    target_language: str
    tone_enabled: bool
    tone_prompt_preset_id: str
    tone_prompt: str


class TonePromptPreset(BaseModel):
    id: str
    label: str
    prompt: str


class PersonalizationAccessResponse(BaseModel):
    available_languages: list[str]
    allow_user_tone_prompt_edit: bool
    tone_prompt_presets: list[TonePromptPreset]


class PersonalizationResponse(BaseModel):
    preferences: UserPreferences
    access: PersonalizationAccessResponse


class UpdatePersonalizationRequest(BaseModel):
    translation_enabled: Optional[bool] = None
    target_language: Optional[str] = Field(None, max_length=100)
    tone_enabled: Optional[bool] = None
    tone_prompt_preset_id: Optional[str] = Field(None, max_length=100)
    tone_prompt: Optional[str] = Field(None, max_length=500)


class UpdatePersonalizationAccessRequest(BaseModel):
    available_languages: Optional[list[str]] = None
    allow_user_tone_prompt_edit: Optional[bool] = None
    tone_prompt_presets: Optional[list[TonePromptPreset]] = None


# ---------------------------------------------------------------------------
# Admin — Tone
# ---------------------------------------------------------------------------

class SetToneRequest(BaseModel):
    tone_name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    strength: Optional[int] = Field(None, ge=0, le=100)


class ToneResponse(BaseModel):
    tone_name: str
    description: str
    strength: int


# ---------------------------------------------------------------------------
# Admin — Model
# ---------------------------------------------------------------------------

class SetModelRequest(BaseModel):
    provider: Optional[str] = Field(None, max_length=50)
    model: Optional[str] = Field(None, max_length=200)
    api_key: Optional[str] = Field(None, max_length=500)
    base_url: Optional[str] = Field(None, max_length=500)
    diffusion: Optional[bool] = None
    max_tokens: Optional[int] = Field(None, ge=1, le=50000)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    timeout: Optional[float] = Field(None, ge=1.0, le=120.0)


class ModelResponse(BaseModel):
    provider: str
    model: str
    has_api_key: bool
    base_url: str
    diffusion: bool
    diffusion_available: bool  # Whether current provider supports real diffusion
    max_tokens: int
    temperature: float
    top_p: float
    frequency_penalty: float
    presence_penalty: float
    timeout: float


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class UserStatsResponse(BaseModel):
    user_id: str
    username: str
    role: str
    joined_at: float
    last_active: float
    total_messages: int
    total_tokens_used: int
    preferences: UserPreferences


class GlobalStatsResponse(BaseModel):
    total_messages: int
    total_tokens: int
    active_users: int
    total_users: int
    connected_clients: int
    users: list[UserStatsResponse]


class MyStatsResponse(BaseModel):
    user_id: str
    username: str
    role: str
    total_messages: int
    total_tokens_used: int
    joined_at: float
    last_active: float
    preferences: UserPreferences


class UserSummaryResponse(BaseModel):
    user_id: str
    username: str
    role: str
    joined_at: float
    last_active: float
    total_messages: int
    total_tokens_used: int
    preferences: UserPreferences


# ---------------------------------------------------------------------------
# Admin — User management
# ---------------------------------------------------------------------------

class SetRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(user|admin)$")


# ---------------------------------------------------------------------------
# Admin — Context management
# ---------------------------------------------------------------------------

class ContextSettingsRequest(BaseModel):
    max_messages: Optional[int] = Field(None, ge=1, le=100000)
    max_tokens_per_user: Optional[int] = Field(None, ge=1, le=10000000)


class ContextStatsResponse(BaseModel):
    message_count: int
    total_tokens: int
    max_messages: int
    max_tokens_per_user: int


# ---------------------------------------------------------------------------
# WebSocket broadcast payload
# ---------------------------------------------------------------------------

class WSChatPayload(BaseModel):
    type: str = "chat"
    user: str
    message: str
    original: Optional[str] = None  # Sent to all clients; frontend controls visibility via showOriginals toggle
    timestamp: float
    tone_name: str
    translation_language: Optional[str] = None
    source_language: Optional[str] = None


# ---------------------------------------------------------------------------
# General
# ---------------------------------------------------------------------------

class StatusResponse(BaseModel):
    status: str = "ok"
    connected_clients: int
    message_count: int
    tone: ToneResponse
    model: ModelResponse


class ProviderPresetsResponse(BaseModel):
    presets: dict[str, dict]


class TonePresetsResponse(BaseModel):
    presets: dict[str, str]
