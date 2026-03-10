"""
Tone-Field Chat — Request / Response Models

Pydantic schemas for all API endpoints.
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
# WebSocket broadcast payload
# ---------------------------------------------------------------------------

class WSChatPayload(BaseModel):
    type: str = "chat"
    user: str
    message: str
    original: Optional[str] = None  # Only included for admin
    timestamp: float
    tone_name: str


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
