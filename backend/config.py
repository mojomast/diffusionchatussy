"""
Tone-Field Chat — Configuration

Holds all runtime configuration for tone profiles, model settings,
and provider definitions. Everything lives in memory for the PoC,
with optional .env loading for API keys.
"""

from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Provider presets — makes it trivial to switch between providers
# ---------------------------------------------------------------------------

PROVIDER_PRESETS: dict[str, dict] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "inception/mercury-2",
        "note": "Access 300+ models including Mercury 2. Use OpenRouter API key.",
    },
    "inception": {
        "base_url": "https://api.inceptionlabs.ai/v1",
        "default_model": "mercury-2",
        "note": "Direct Inception API. Fastest path to Mercury dLLMs.",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-5-sonnet-20241022",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Llama-3-70b-chat-hf",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.1-70b-versatile",
    },
    "local": {
        "base_url": "http://localhost:1234/v1",
        "default_model": "local-model",
    },
    "custom": {
        "base_url": "",
        "default_model": "",
    },
}


# ---------------------------------------------------------------------------
# Tone preset library
# ---------------------------------------------------------------------------

TONE_PRESETS: dict[str, str] = {
    "friendly": "Casual, polite, and collaborative. Use warm language.",
    "professional": "Formal, clear, and respectful. Suitable for a workplace.",
    "sarcastic": "Witty and sarcastic, but not mean-spirited.",
    "academic": "Calm, analytical, and scholarly. Use precise language.",
    "chaotic": "Unpredictable, playful, and energetic. Surprise the reader.",
    "supportive": "Encouraging, empathetic, and kind. Focus on positivity.",
    "concise": "Extremely brief. Strip all fluff. Get to the point.",
    "poetic": "Lyrical, metaphorical, and expressive. Beauty in language.",
}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ToneConfig(BaseModel):
    """Active tone profile."""
    tone_name: str = "friendly"
    description: str = TONE_PRESETS.get("friendly", "")
    strength: int = Field(
        default=100,
        ge=0,
        le=100,
        description="0 = raw (no rewrite), 100 = full tone rewrite",
    )


class ModelConfig(BaseModel):
    """Active LLM model configuration with granular controls."""
    provider: str = "openrouter"
    model: str = "inception/mercury-2"
    api_key: str = ""
    base_url: str = ""  # If empty, resolved from provider preset
    diffusion: bool = Field(
        default=False,
        description=(
            "Enable real diffusion streaming (Mercury 2 via Inception API only). "
            "Streams intermediate denoising steps to the frontend."
        ),
    )
    max_tokens: int = Field(
        default=1024,
        ge=1,
        le=50000,
        description="Max tokens for the rewrite response",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    top_p: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling top-p",
    )
    frequency_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Frequency penalty",
    )
    presence_penalty: float = Field(
        default=0.0,
        ge=-2.0,
        le=2.0,
        description="Presence penalty",
    )
    timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Request timeout in seconds",
    )

    def resolved_base_url(self) -> str:
        """Return the base URL, falling back to the provider preset."""
        if self.base_url:
            return self.base_url.rstrip("/")
        preset = PROVIDER_PRESETS.get(self.provider, {})
        return preset.get("base_url", "").rstrip("/")


class AppState:
    """
    In-memory application state.
    Holds messages, tone config, model config, and connected clients.
    """

    def __init__(self) -> None:
        self.tone = ToneConfig()
        self.model = ModelConfig()
        self.messages: list[dict] = []
        self.websocket_clients: list = []

        # Try to pick up API key from environment
        env_key = os.getenv("LLM_API_KEY", "")
        if env_key:
            self.model.api_key = env_key

    def set_tone(self, tone_name: str, description: Optional[str] = None, strength: Optional[int] = None) -> ToneConfig:
        """Update tone profile."""
        self.tone.tone_name = tone_name
        if description is not None:
            self.tone.description = description
        elif tone_name in TONE_PRESETS:
            self.tone.description = TONE_PRESETS[tone_name]
        if strength is not None:
            self.tone.strength = max(0, min(100, strength))
        return self.tone

    def set_model(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        diffusion: Optional[bool] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        timeout: Optional[float] = None,
    ) -> ModelConfig:
        """Update model configuration. Only provided fields are changed."""
        if provider is not None:
            self.model.provider = provider
            # When switching provider, default the model if not specified
            if model is None:
                preset = PROVIDER_PRESETS.get(provider, {})
                self.model.model = preset.get("default_model", self.model.model)
        if model is not None:
            self.model.model = model
        if api_key is not None:
            self.model.api_key = api_key
        if base_url is not None:
            self.model.base_url = base_url
        if diffusion is not None:
            self.model.diffusion = diffusion
        if max_tokens is not None:
            self.model.max_tokens = max(1, min(4096, max_tokens))
        if temperature is not None:
            self.model.temperature = max(0.0, min(2.0, temperature))
        if top_p is not None:
            self.model.top_p = max(0.0, min(1.0, top_p))
        if frequency_penalty is not None:
            self.model.frequency_penalty = max(-2.0, min(2.0, frequency_penalty))
        if presence_penalty is not None:
            self.model.presence_penalty = max(-2.0, min(2.0, presence_penalty))
        if timeout is not None:
            self.model.timeout = max(1.0, min(120.0, timeout))
        return self.model

    def add_message(self, msg: dict) -> None:
        self.messages.append(msg)

    def get_messages(self, limit: int = 100) -> list[dict]:
        return self.messages[-limit:]


# Singleton — imported by other modules
state = AppState()
