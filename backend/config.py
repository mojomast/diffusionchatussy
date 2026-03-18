"""
Tone-Field Chat — Configuration

Holds all runtime configuration for tone profiles, model settings,
provider definitions, user sessions, and rate limiting.
Everything lives in memory for the PoC, with optional .env loading for API keys.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
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
# Personalization defaults
# ---------------------------------------------------------------------------

DEFAULT_ALLOWED_LANGUAGES: list[str] = [
    "English",
    "Spanish",
    "French",
    "German",
    "Portuguese",
    "Japanese",
    "Korean",
    "Arabic",
    "Hindi",
    "Mandarin Chinese",
]

DEFAULT_TONE_PROMPT_PRESETS: list[dict[str, str]] = [
    {"id": "none", "label": "No extra prompt", "prompt": ""},
    {"id": "gentle", "label": "Gentle and calm", "prompt": "Keep the tone soft, patient, and emotionally safe."},
    {"id": "playful", "label": "Playful", "prompt": "Lean playful, lively, and lightly humorous without becoming chaotic."},
    {"id": "direct", "label": "Direct", "prompt": "Favor clarity and directness over flourish while preserving warmth."},
]

STATE_FILE = Path(__file__).resolve().parent / "data" / "state.json"


def _normalize_languages(languages: list[str]) -> list[str]:
    """Trim, dedupe, and preserve order for admin-managed language options."""
    normalized: list[str] = []
    seen: set[str] = set()

    for language in languages:
        clean = language.strip()
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        normalized.append(clean)
        seen.add(key)

    return normalized or DEFAULT_ALLOWED_LANGUAGES.copy()


def _normalize_tone_prompt_presets(presets: list[dict]) -> list[dict[str, str]]:
    """Normalize admin-managed tone prompt presets."""
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()

    for preset in presets:
        preset_id = str(preset.get("id", "")).strip()[:100]
        label = str(preset.get("label", "")).strip()[:100]
        prompt = str(preset.get("prompt", "")).strip()[:500]
        if not preset_id or not label:
            continue
        key = preset_id.casefold()
        if key in seen:
            continue
        normalized.append({"id": preset_id, "label": label, "prompt": prompt})
        seen.add(key)

    if not normalized:
        return [preset.copy() for preset in DEFAULT_TONE_PROMPT_PRESETS]

    if "none" not in {preset["id"].casefold() for preset in normalized}:
        normalized.insert(0, DEFAULT_TONE_PROMPT_PRESETS[0].copy())

    return normalized


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ToneConfig(BaseModel):
    """Active tone profile."""
    tone_name: str = "friendly"
    description: str = TONE_PRESETS.get("friendly", "")
    strength: int = Field(default=100, ge=0, le=100, description="0 = raw (no rewrite), 100 = full tone rewrite")


class ModelConfig(BaseModel):
    """Active LLM model configuration with granular controls."""
    provider: str = "openrouter"
    model: str = "inception/mercury-2"
    api_key: str = ""
    base_url: str = ""
    diffusion: bool = Field(default=False)
    max_tokens: int = Field(default=1024, ge=1, le=50000)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: float = Field(default=0.0, ge=-2.0, le=2.0)
    timeout: float = Field(default=30.0, ge=1.0, le=120.0)

    def resolved_base_url(self) -> str:
        if self.base_url:
            return self.base_url.rstrip("/")
        preset = PROVIDER_PRESETS.get(self.provider, {})
        return preset.get("base_url", "").rstrip("/")


class PersonalizationAccessConfig(BaseModel):
    available_languages: list[str] = Field(default_factory=lambda: DEFAULT_ALLOWED_LANGUAGES.copy())
    allow_user_tone_prompt_edit: bool = True
    tone_prompt_presets: list[dict[str, str]] = Field(default_factory=lambda: [preset.copy() for preset in DEFAULT_TONE_PROMPT_PRESETS])


class AppState:
    def __init__(self) -> None:
        self.tone = ToneConfig()
        self.model = ModelConfig()
        self.personalization = PersonalizationAccessConfig()
        self.messages: list[dict] = []
        self.websocket_clients: list = []
        self.websocket_sessions: dict[int, Optional[str]] = {}
        self.users: dict[str, dict] = {}
        self.context_settings: dict[str, int] = {
            "max_messages": 500,
            "max_tokens_per_user": 100000,
        }
        self.rate_limits: dict[str, list[float]] = {}
        self.global_stats: dict[str, int] = {
            "total_tokens": 0,
            "total_messages": 0,
        }

        env_key = os.getenv("LLM_API_KEY", "")
        if env_key:
            self.model.api_key = env_key

        self.load_state()

    def default_target_language(self) -> str:
        if self.personalization.available_languages:
            return self.personalization.available_languages[0]
        return DEFAULT_ALLOWED_LANGUAGES[0]

    def default_tone_prompt_preset_id(self) -> str:
        if self.personalization.tone_prompt_presets:
            return self.personalization.tone_prompt_presets[0]["id"]
        return DEFAULT_TONE_PROMPT_PRESETS[0]["id"]

    def get_tone_prompt_preset(self, preset_id: str) -> Optional[dict[str, str]]:
        wanted = preset_id.strip().casefold()
        for preset in self.personalization.tone_prompt_presets:
            if preset["id"].casefold() == wanted:
                return preset
        return None

    def sanitize_user_preferences(self, user: dict) -> None:
        prefs = user.setdefault("preferences", {})
        prefs.setdefault("translation_enabled", False)
        prefs.setdefault("target_language", self.default_target_language())
        prefs.setdefault("tone_enabled", True)
        prefs.setdefault("tone_prompt_preset_id", self.default_tone_prompt_preset_id())
        prefs.setdefault("tone_prompt", "")

        target_language = str(prefs.get("target_language", "")).strip()
        if target_language not in self.personalization.available_languages:
            prefs["target_language"] = self.default_target_language()
        else:
            prefs["target_language"] = target_language

        prefs["translation_enabled"] = bool(prefs.get("translation_enabled", False))
        prefs["tone_enabled"] = bool(prefs.get("tone_enabled", True))

        preset_id = str(prefs.get("tone_prompt_preset_id", "")).strip()
        if not self.get_tone_prompt_preset(preset_id):
            prefs["tone_prompt_preset_id"] = self.default_tone_prompt_preset_id()
        else:
            prefs["tone_prompt_preset_id"] = preset_id

        prefs["tone_prompt"] = str(prefs.get("tone_prompt", "")).strip()[:500]
        if not self.personalization.allow_user_tone_prompt_edit:
            prefs["tone_prompt"] = ""

    def serialize_state(self) -> dict:
        return {
            "tone": self.tone.model_dump(),
            "model": self.model.model_dump(),
            "personalization": self.personalization.model_dump(),
            "context_settings": self.context_settings,
            "global_stats": self.global_stats,
            "users": self.users,
        }

    def save_state(self) -> None:
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(self.serialize_state(), indent=2), encoding="utf-8")
        except Exception:
            pass

    def load_state(self) -> None:
        if not STATE_FILE.exists():
            return

        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return

        if isinstance(data.get("tone"), dict):
            self.tone = ToneConfig(**data["tone"])
        if isinstance(data.get("model"), dict):
            loaded_model = ModelConfig(**data["model"])
            if not loaded_model.api_key:
                loaded_model.api_key = self.model.api_key
            self.model = loaded_model
        if isinstance(data.get("personalization"), dict):
            personalization = data["personalization"].copy()
            personalization["available_languages"] = _normalize_languages(personalization.get("available_languages", []))
            personalization["tone_prompt_presets"] = _normalize_tone_prompt_presets(personalization.get("tone_prompt_presets", []))
            self.personalization = PersonalizationAccessConfig(**personalization)
        if isinstance(data.get("context_settings"), dict):
            self.context_settings.update({
                "max_messages": int(data["context_settings"].get("max_messages", self.context_settings["max_messages"])),
                "max_tokens_per_user": int(data["context_settings"].get("max_tokens_per_user", self.context_settings["max_tokens_per_user"])),
            })
        if isinstance(data.get("global_stats"), dict):
            self.global_stats.update({
                "total_tokens": int(data["global_stats"].get("total_tokens", 0)),
                "total_messages": int(data["global_stats"].get("total_messages", 0)),
            })
        if isinstance(data.get("users"), dict):
            self.users = data["users"]
            for user in self.users.values():
                self.sanitize_user_preferences(user)
        self.save_state()

    def set_tone(self, tone_name: str, description: Optional[str] = None, strength: Optional[int] = None) -> ToneConfig:
        self.tone.tone_name = tone_name
        if description is not None:
            self.tone.description = description
        elif tone_name in TONE_PRESETS:
            self.tone.description = TONE_PRESETS[tone_name]
        if strength is not None:
            self.tone.strength = max(0, min(100, strength))
        self.save_state()
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
        if provider is not None:
            self.model.provider = provider
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
        self.save_state()
        return self.model

    def set_personalization(
        self,
        available_languages: Optional[list[str]] = None,
        allow_user_tone_prompt_edit: Optional[bool] = None,
        tone_prompt_presets: Optional[list[dict[str, str]]] = None,
    ) -> PersonalizationAccessConfig:
        if available_languages is not None:
            self.personalization.available_languages = _normalize_languages(available_languages)
        if allow_user_tone_prompt_edit is not None:
            self.personalization.allow_user_tone_prompt_edit = allow_user_tone_prompt_edit
        if tone_prompt_presets is not None:
            self.personalization.tone_prompt_presets = _normalize_tone_prompt_presets(tone_prompt_presets)

        for user in self.users.values():
            self.sanitize_user_preferences(user)

        self.save_state()
        return self.personalization

    def add_message(self, msg: dict) -> None:
        self.messages.append(msg)
        max_msgs = self.context_settings["max_messages"]
        if len(self.messages) > max_msgs:
            overflow = len(self.messages) - max_msgs
            self.messages = self.messages[overflow:]
        self.save_state()

    def get_messages(self, limit: int = 100) -> list[dict]:
        return self.messages[-limit:]

    def check_rate_limit(self, session_id: str) -> bool:
        now = time.time()
        window = RATE_LIMIT_WINDOW_SECONDS

        if session_id not in self.rate_limits:
            self.rate_limits[session_id] = []

        self.rate_limits[session_id] = [
            ts for ts in self.rate_limits[session_id]
            if now - ts < window
        ]

        if len(self.rate_limits[session_id]) >= RATE_LIMIT_MAX_MESSAGES:
            return False

        self.rate_limits[session_id].append(now)
        return True

    def get_or_create_user(self, session_id: str, username: str = "Anonymous") -> dict:
        if session_id in self.users:
            user = self.users[session_id]
            user["last_active"] = time.time()
            self.sanitize_user_preferences(user)
            return user

        user = {
            "user_id": session_id,
            "username": username,
            "role": "user",
            "joined_at": time.time(),
            "last_active": time.time(),
            "total_messages": 0,
            "total_tokens_used": 0,
            "preferences": {
                "translation_enabled": False,
                "target_language": self.default_target_language(),
                "tone_enabled": True,
                "tone_prompt_preset_id": self.default_tone_prompt_preset_id(),
                "tone_prompt": "",
            },
        }
        self.sanitize_user_preferences(user)
        self.users[session_id] = user
        self.save_state()
        return user

    def get_user(self, session_id: str) -> Optional[dict]:
        user = self.users.get(session_id)
        if user:
            self.sanitize_user_preferences(user)
        return user

    def remove_user(self, session_id: str) -> bool:
        if session_id in self.users:
            del self.users[session_id]
            self.rate_limits.pop(session_id, None)
            self.save_state()
            return True
        return False

    def update_user_stats(self, session_id: str, tokens_used: int) -> None:
        user = self.users.get(session_id)
        if user:
            user["total_messages"] += 1
            user["total_tokens_used"] += tokens_used
            user["last_active"] = time.time()

        self.global_stats["total_messages"] += 1
        self.global_stats["total_tokens"] += tokens_used
        self.save_state()

    def check_token_limit(self, session_id: str) -> bool:
        user = self.users.get(session_id)
        if not user:
            return True
        max_tokens = self.context_settings["max_tokens_per_user"]
        return user["total_tokens_used"] < max_tokens

    def get_active_user_count(self) -> int:
        cutoff = time.time() - 300
        return sum(1 for u in self.users.values() if u["last_active"] > cutoff)


# Singleton — imported by other modules
state = AppState()
