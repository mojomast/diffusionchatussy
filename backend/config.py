"""
Tone-Field Chat — Configuration

Holds all runtime configuration for tone profiles, model settings,
provider definitions, user sessions, and rate limiting.
Everything lives in memory for the PoC, with optional .env loading for API keys.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file from the working directory (backend/)
load_dotenv()


# ---------------------------------------------------------------------------
# Admin password (configurable via env var)
# ---------------------------------------------------------------------------

ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "h4x0r")


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
# Recommended OpenRouter models for tone rewriting
# ---------------------------------------------------------------------------
# Criteria: cheap, fast, creative, instruction-following, minimal censorship.
# Each message = 1 LLM call, so cost and latency are critical.

OPENROUTER_FAVORITES: list[dict[str, str]] = [
    {
        "id": "inception/mercury-2",
        "name": "Inception: Mercury 2",
        "why": "The default. Fastest model on OpenRouter (~1000 tok/s), diffusion LLM, very cheap. Great at short rewrites.",
    },
    {
        "id": "google/gemini-2.0-flash-001",
        "name": "Google: Gemini 2.0 Flash",
        "why": "Extremely fast, 1M context, strong instruction following. $0.10/$0.40 per 1M tokens.",
    },
    {
        "id": "google/gemini-2.5-flash-lite",
        "name": "Google: Gemini 2.5 Flash Lite",
        "why": "Cheapest Gemini, ultra-low latency. Great for high-volume chat rewriting.",
    },
    {
        "id": "openai/gpt-4o-mini",
        "name": "OpenAI: GPT-4o-mini",
        "why": "Reliable instruction follower, fast, affordable. Won't refuse most creative rewrites.",
    },
    {
        "id": "openai/gpt-4.1-nano",
        "name": "OpenAI: GPT-4.1 Nano",
        "why": "Fastest and cheapest GPT. $0.10/$0.40 per 1M tokens, 1M context. Built for low-latency.",
    },
    {
        "id": "mistralai/mistral-small-3.2-24b-instruct",
        "name": "Mistral: Mistral Small 3.2 24B",
        "why": "Fast 24B model, excellent at style tasks. Less censored than OpenAI. $0.06/$0.18 per 1M.",
    },
    {
        "id": "meta-llama/llama-3.3-70b-instruct",
        "name": "Meta: Llama 3.3 70B Instruct",
        "why": "Strong open model, great creative writing. Low censorship. $0.10/$0.32 per 1M.",
    },
    {
        "id": "qwen/qwen3-30b-a3b",
        "name": "Qwen: Qwen3 30B A3B",
        "why": "MoE with only 3B active params = very fast. Strong multilingual style transfer. $0.08/$0.28 per 1M.",
    },
    {
        "id": "deepseek/deepseek-chat-v3-0324",
        "name": "DeepSeek: V3 0324",
        "why": "The roleplay king. Excellent creative writing, uncensored, great instruction following. $0.20/$0.77 per 1M.",
    },
    {
        "id": "deepseek/deepseek-chat",
        "name": "DeepSeek: DeepSeek V3",
        "why": "671B MoE powerhouse, great at nuanced rewrites. $0.32/$0.89 per 1M — still cheap per message.",
    },
    {
        "id": "mistralai/mistral-small-creative",
        "name": "Mistral: Mistral Small Creative",
        "why": "Purpose-built for creative writing and roleplay. Ideal for poetic/chaotic tones. $0.10/$0.30 per 1M.",
    },
]


# ---------------------------------------------------------------------------
# Rate limiting config
# ---------------------------------------------------------------------------

RATE_LIMIT_MAX_MESSAGES: int = 10
RATE_LIMIT_WINDOW_SECONDS: float = 60.0


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
    Holds messages, tone config, model config, connected clients,
    user sessions, rate limits, and global stats.
    """

    def __init__(self) -> None:
        self.tone = ToneConfig()
        self.model = ModelConfig()
        self.messages: list[dict] = []
        self.websocket_clients: list = []

        # --- User sessions: session_id -> user info dict ---
        # Each user dict: {user_id, username, role, joined_at, last_active,
        #                   total_messages, total_tokens_used}
        self.users: dict[str, dict] = {}

        # --- Context management settings ---
        self.context_settings: dict[str, int] = {
            "max_messages": 500,
            "max_tokens_per_user": 100000,
        }

        # --- Rate limiting: session_id -> list of message timestamps ---
        self.rate_limits: dict[str, list[float]] = {}

        # --- Global stats ---
        self.global_stats: dict[str, int] = {
            "total_tokens": 0,
            "total_messages": 0,
        }

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
            self.model.max_tokens = max(1, min(50000, max_tokens))
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
        """Add a message, enforcing max_messages context limit."""
        self.messages.append(msg)
        max_msgs = self.context_settings["max_messages"]
        if len(self.messages) > max_msgs:
            # Drop the oldest messages to stay within the limit
            overflow = len(self.messages) - max_msgs
            self.messages = self.messages[overflow:]

    def get_messages(self, limit: int = 100) -> list[dict]:
        return self.messages[-limit:]

    # --- Rate limiting helpers ---

    def check_rate_limit(self, session_id: str) -> bool:
        """
        Check if a user has exceeded the rate limit.
        Returns True if the user is within limits, False if rate-limited.
        """
        now = time.time()
        window = RATE_LIMIT_WINDOW_SECONDS

        if session_id not in self.rate_limits:
            self.rate_limits[session_id] = []

        # Prune timestamps outside the window
        self.rate_limits[session_id] = [
            ts for ts in self.rate_limits[session_id]
            if now - ts < window
        ]

        if len(self.rate_limits[session_id]) >= RATE_LIMIT_MAX_MESSAGES:
            return False  # Rate limited

        # Record this message timestamp
        self.rate_limits[session_id].append(now)
        return True

    # --- User session helpers ---

    def get_or_create_user(self, session_id: str, username: str = "Anonymous") -> dict:
        """Get existing user or create a new one for this session."""
        if session_id in self.users:
            user = self.users[session_id]
            user["last_active"] = time.time()
            return user

        user = {
            "user_id": session_id,
            "username": username,
            "role": "user",
            "joined_at": time.time(),
            "last_active": time.time(),
            "total_messages": 0,
            "total_tokens_used": 0,
        }
        self.users[session_id] = user
        return user

    def get_user(self, session_id: str) -> Optional[dict]:
        """Get user by session ID, or None if not found."""
        return self.users.get(session_id)

    def remove_user(self, session_id: str) -> bool:
        """Remove a user session. Returns True if removed."""
        if session_id in self.users:
            del self.users[session_id]
            # Also clean up rate limits
            self.rate_limits.pop(session_id, None)
            return True
        return False

    def update_user_stats(self, session_id: str, tokens_used: int) -> None:
        """Update token and message stats for a user and globally."""
        user = self.users.get(session_id)
        if user:
            user["total_messages"] += 1
            user["total_tokens_used"] += tokens_used
            user["last_active"] = time.time()

        self.global_stats["total_messages"] += 1
        self.global_stats["total_tokens"] += tokens_used

    def check_token_limit(self, session_id: str) -> bool:
        """
        Check if a user has exceeded their token limit.
        Returns True if within limits, False if exceeded.
        """
        user = self.users.get(session_id)
        if not user:
            return True  # No user record = no limit enforced yet
        max_tokens = self.context_settings["max_tokens_per_user"]
        return user["total_tokens_used"] < max_tokens

    def get_active_user_count(self) -> int:
        """Count users active in the last 5 minutes."""
        cutoff = time.time() - 300  # 5 minutes
        return sum(1 for u in self.users.values() if u["last_active"] > cutoff)


# Singleton — imported by other modules
state = AppState()
