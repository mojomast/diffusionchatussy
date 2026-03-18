"""
Tone-Field Chat — FastAPI Backend

Single-file server with:
- REST endpoints for chat, admin tone, admin model config
- WebSocket endpoint for realtime message broadcasting
- Real diffusion streaming: Mercury 2 denoising steps broadcast live to clients
- CORS middleware for local frontend dev
- User session system with cookie-based auth
- Token tracking and rate limiting
- Admin auth and user management
- Context management with configurable limits
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from difflib import SequenceMatcher

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Request, Response, HTTPException, Depends, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import httpx

from config import (
    state, PROVIDER_PRESETS, TONE_PRESETS, OPENROUTER_FAVORITES,
    ADMIN_PASSWORD, RATE_LIMIT_MAX_MESSAGES, RATE_LIMIT_WINDOW_SECONDS,
)
from models import (
    SendMessageRequest,
    ChatMessage,
    SetToneRequest,
    ToneResponse,
    SetModelRequest,
    ModelResponse,
    StatusResponse,
    ProviderPresetsResponse,
    TonePresetsResponse,
    JoinRequest,
    AdminAuthRequest,
    SessionResponse,
    UserPreferences,
    UserSummaryResponse,
    TonePromptPreset,
    PersonalizationAccessResponse,
    PersonalizationResponse,
    UpdatePersonalizationRequest,
    UpdatePersonalizationAccessRequest,
    GlobalStatsResponse,
    MyStatsResponse,
    UserStatsResponse,
    SetRoleRequest,
    ContextSettingsRequest,
    ContextStatsResponse,
)
from llm import rewrite_message, rewrite_message_diffusion, supports_diffusion, estimate_tokens, transform_message

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("tonechat")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_COOKIE_NAME = "tonechat_session"
SESSION_COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days in seconds


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info("ToneChat backend starting up")
    logger.info(f"  Tone: {state.tone.tone_name} ({state.tone.strength}%)")
    logger.info(f"  Model: {state.model.provider}/{state.model.model}")
    logger.info(f"  Diffusion: {state.model.diffusion}")
    logger.info(f"  API key configured: {bool(state.model.api_key)}")
    logger.info(f"  Admin password configured: {'(custom)' if ADMIN_PASSWORD != 'h4x0r' else '(default)'}")
    yield
    logger.info("ToneChat backend shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ToneChat",
    description="Tone-Field Chat — messages rewritten by LLM to match a tone profile",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _get_session_id(request: Request) -> Optional[str]:
    """Extract session ID from cookie."""
    return request.cookies.get(SESSION_COOKIE_NAME)


def _set_session_cookie(response: Response, session_id: str) -> None:
    """Set the session cookie on a response."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def _get_or_create_session(request: Request) -> tuple[str, dict, bool]:
    """
    Get existing session or create a new one.
    Returns (session_id, user_dict, is_new).
    """
    session_id = _get_session_id(request)
    is_new = False

    if session_id and session_id in state.users:
        user = state.users[session_id]
        user["last_active"] = time.time()
        return session_id, user, False

    # Create new session
    session_id = str(uuid.uuid4())
    user = state.get_or_create_user(session_id, "Anonymous")
    is_new = True
    return session_id, user, is_new


def _require_session(request: Request) -> tuple[str, dict]:
    """
    Require a valid session. Raises 401 if no session found.
    Returns (session_id, user_dict).
    """
    session_id = _get_session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="No session cookie. Call /auth/session or /auth/join first.")

    user = state.get_user(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Call /auth/session or /auth/join first.")

    user["last_active"] = time.time()
    return session_id, user


def _require_admin(request: Request) -> tuple[str, dict]:
    """
    Require admin role. Raises 401/403 if not authenticated or not admin.
    Returns (session_id, user_dict).
    """
    session_id, user = _require_session(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return session_id, user


# ---------------------------------------------------------------------------
# Helper: build model response (never leak the API key)
# ---------------------------------------------------------------------------

def _model_response() -> ModelResponse:
    m = state.model
    return ModelResponse(
        provider=m.provider,
        model=m.model,
        has_api_key=bool(m.api_key),
        base_url=m.resolved_base_url(),
        diffusion=m.diffusion,
        diffusion_available=supports_diffusion(m),
        max_tokens=m.max_tokens,
        temperature=m.temperature,
        top_p=m.top_p,
        frequency_penalty=m.frequency_penalty,
        presence_penalty=m.presence_penalty,
        timeout=m.timeout,
    )


def _tone_response() -> ToneResponse:
    t = state.tone
    return ToneResponse(
        tone_name=t.tone_name,
        description=t.description,
        strength=t.strength,
    )


def _session_response(user: dict) -> SessionResponse:
    state.sanitize_user_preferences(user)
    return SessionResponse(
        user_id=user["user_id"],
        username=user["username"],
        role=user["role"],
        joined_at=user["joined_at"],
        last_active=user["last_active"],
        total_messages=user["total_messages"],
        total_tokens_used=user["total_tokens_used"],
        preferences=UserPreferences(**user["preferences"]),
    )


def _personalization_access_response() -> PersonalizationAccessResponse:
    return PersonalizationAccessResponse(
        available_languages=state.personalization.available_languages,
        allow_user_tone_prompt_edit=state.personalization.allow_user_tone_prompt_edit,
        tone_prompt_presets=[TonePromptPreset(**preset) for preset in state.personalization.tone_prompt_presets],
    )


def _personalization_response(user: dict) -> PersonalizationResponse:
    state.sanitize_user_preferences(user)
    return PersonalizationResponse(
        preferences=UserPreferences(**user["preferences"]),
        access=_personalization_access_response(),
    )


def _user_transform_signature(user: Optional[dict]) -> tuple[bool, str, bool, str]:
    """Return a stable personalization key for a recipient."""
    if not user:
        return False, "", True, ""

    state.sanitize_user_preferences(user)
    prefs = user["preferences"]
    translation_enabled = bool(prefs.get("translation_enabled", False))
    target_language = prefs.get("target_language", "") if translation_enabled else ""
    tone_enabled = bool(prefs.get("tone_enabled", True))
    tone_prompt = ""
    preset_id = str(prefs.get("tone_prompt_preset_id", "")).strip()
    preset = state.get_tone_prompt_preset(preset_id)
    if preset and preset.get("prompt"):
        tone_prompt = preset["prompt"]

    if tone_enabled and state.personalization.allow_user_tone_prompt_edit:
        custom_prompt = str(prefs.get("tone_prompt", "")).strip()
        tone_prompt = "\n".join(part for part in [tone_prompt, custom_prompt] if part)

    return translation_enabled, target_language, tone_enabled, tone_prompt


def _is_default_transform_signature(signature: tuple[bool, str, bool, str]) -> bool:
    """Check whether a recipient can reuse the canonical room-tone output."""
    return signature == (False, "", True, "")


def _update_user_preferences(user: dict, req: UpdatePersonalizationRequest) -> None:
    """Apply validated personalization changes to a user record."""
    state.sanitize_user_preferences(user)
    prefs = user["preferences"]

    if req.translation_enabled is not None:
        prefs["translation_enabled"] = req.translation_enabled

    if req.target_language is not None:
        target_language = req.target_language.strip()
        if target_language not in state.personalization.available_languages:
            raise HTTPException(status_code=400, detail="Selected language is not available.")
        prefs["target_language"] = target_language

    if req.tone_enabled is not None:
        prefs["tone_enabled"] = req.tone_enabled

    if req.tone_prompt_preset_id is not None:
        preset_id = req.tone_prompt_preset_id.strip()
        if not state.get_tone_prompt_preset(preset_id):
            raise HTTPException(status_code=400, detail="Selected tone prompt preset is not available.")
        prefs["tone_prompt_preset_id"] = preset_id

    if req.tone_prompt is not None:
        if not state.personalization.allow_user_tone_prompt_edit:
            raise HTTPException(status_code=403, detail="Custom tone prompts are disabled by admin.")
        prefs["tone_prompt"] = req.tone_prompt.strip()[:500]

    state.sanitize_user_preferences(user)
    state.save_state()


def _guess_language_name(text: str) -> str:
    """Cheap heuristic for source-language labels shown in the UI."""
    lowered = text.lower()
    if any(char in text for char in "abcdefghijklmnopqrstuvwxyz"):
        if any(word in lowered for word in [" the ", " and ", " you ", " are ", " this "]):
            return "English"
        if any(word in lowered for word in [" el ", " la ", " que ", " gracias", " por "]):
            return "Spanish"
        if any(word in lowered for word in [" le ", " la ", " merci", " avec ", " bonjour"]):
            return "French"
    if any("\u3040" <= char <= "\u30ff" for char in text):
        return "Japanese"
    if any("\uac00" <= char <= "\ud7af" for char in text):
        return "Korean"
    if any("\u0600" <= char <= "\u06ff" for char in text):
        return "Arabic"
    if any("\u4e00" <= char <= "\u9fff" for char in text):
        return "Chinese"
    return "Original"


async def _build_personalized_chat_payload(
    msg: ChatMessage,
    msg_id: str,
    signature: tuple[bool, str, bool, str],
    use_diffusion: bool,
    rewrite_status: str,
    total_tokens: int,
) -> dict:
    """Build the final chat payload for one personalization bucket."""
    translation_enabled, target_language, tone_enabled, tone_prompt = signature

    if _is_default_transform_signature(signature):
        message_text = msg.rewritten
        personal_status = rewrite_status if not use_diffusion else "ok"
    else:
        transformed = await transform_message(
            msg.original,
            tone=state.tone,
            tone_enabled=tone_enabled,
            target_language=target_language if translation_enabled else None,
            custom_tone_prompt=tone_prompt,
            source_language=msg.source_language,
        )
        message_text = transformed.get("rewritten", msg.original)
        personal_status = transformed.get("rewrite_status", "ok")

    if translation_enabled and msg.source_language and target_language.casefold() == msg.source_language.casefold():
        message_text = msg.original

    return {
        "type": "chat",
        "msg_id": msg_id,
        "user": msg.user,
        "message": message_text,
        "original": msg.original,
        "timestamp": msg.timestamp,
        "tone_name": msg.tone_name if tone_enabled and state.tone.strength > 0 else "",
        "diffused": use_diffusion if _is_default_transform_signature(signature) else False,
        "rewrite_status": personal_status,
        "token_estimate": total_tokens,
        "tone_applied": tone_enabled and state.tone.strength > 0,
        "translation_language": target_language if translation_enabled else None,
        "source_language": msg.source_language,
    }


async def broadcast_room_tone_only(payload: dict) -> None:
    """Broadcast an event only to clients using the default room transform."""
    dead: list[WebSocket] = []
    message_text = json.dumps(payload)

    for ws in state.websocket_clients:
        session_id = state.websocket_sessions.get(id(ws))
        recipient = state.get_user(session_id) if session_id else None
        if not _is_default_transform_signature(_user_transform_signature(recipient)):
            continue
        try:
            await ws.send_text(message_text)
        except Exception:
            dead.append(ws)

    for ws in dead:
        if ws in state.websocket_clients:
            state.websocket_clients.remove(ws)
        state.websocket_sessions.pop(id(ws), None)


async def broadcast_chat_message(
    msg: ChatMessage,
    msg_id: str,
    use_diffusion: bool,
    rewrite_status: str,
    total_tokens: int,
) -> None:
    """Broadcast a chat message, personalizing translation and tone per recipient."""
    buckets: dict[tuple[bool, str, bool, str], list[WebSocket]] = {}

    for ws in state.websocket_clients:
        session_id = state.websocket_sessions.get(id(ws))
        recipient = state.get_user(session_id) if session_id else None
        signature = _user_transform_signature(recipient)
        buckets.setdefault(signature, []).append(ws)

    payloads = await asyncio.gather(*[
        _build_personalized_chat_payload(msg, msg_id, signature, use_diffusion, rewrite_status, total_tokens)
        for signature in buckets
    ])
    payload_map = dict(zip(buckets.keys(), payloads, strict=False))

    dead: list[WebSocket] = []
    for signature, sockets in buckets.items():
        message_text = json.dumps(payload_map[signature])
        for ws in sockets:
            try:
                await ws.send_text(message_text)
            except Exception:
                dead.append(ws)

    for ws in dead:
        if ws in state.websocket_clients:
            state.websocket_clients.remove(ws)
        state.websocket_sessions.pop(id(ws), None)

# ---------------------------------------------------------------------------
# WebSocket broadcast
# ---------------------------------------------------------------------------

async def broadcast(payload: dict) -> None:
    """Send a JSON payload to all connected WebSocket clients."""
    dead: list[WebSocket] = []
    message_text = json.dumps(payload)

    for ws in state.websocket_clients:
        try:
            await ws.send_text(message_text)
        except Exception:
            dead.append(ws)

    for ws in dead:
        if ws in state.websocket_clients:
            state.websocket_clients.remove(ws)
        state.websocket_sessions.pop(id(ws), None)


def _is_echo_of_recent_rewrite(message: str, lookback: int = 20) -> bool:
    """
    Detect if an incoming message is a copy-paste of a recent rewrite output.
    
    This prevents the recursive rewrite loop where users feed rewritten text
    back as input, causing escalating LLM outputs (e.g. the "sighing" loop).
    
    Returns True if the message is >85% similar to any recent rewrite.
    """
    recent = state.get_messages(lookback)
    msg_lower = message.lower().strip()
    
    for stored in recent:
        rewritten = stored.get("rewritten", "")
        if not rewritten:
            continue
        rewritten_lower = rewritten.lower().strip()
        
        # Exact match
        if msg_lower == rewritten_lower:
            return True
        
        # Fuzzy match — catches minor edits to copy-pasted rewrites
        if len(msg_lower) > 20 and len(rewritten_lower) > 20:
            ratio = SequenceMatcher(None, msg_lower, rewritten_lower).ratio()
            if ratio > 0.85:
                return True
    
    return False


# ---------------------------------------------------------------------------
# Core: process a message (with or without diffusion streaming)
# ---------------------------------------------------------------------------

async def _process_message(user: str, message: str, session_id: Optional[str] = None) -> ChatMessage:
    """
    Process a chat message through the rewrite pipeline.

    If diffusion is enabled and the provider supports it:
      1. Broadcast a `diffusion_start` event
      2. Stream each denoising step as `diffusion_step` events
      3. Broadcast the final `chat` event

    Otherwise: standard rewrite + broadcast.
    
    Includes token tracking and rate limiting when session_id is provided.
    """

    timestamp = time.time()
    msg_id = str(uuid.uuid4())[:8]
    use_diffusion = state.model.diffusion and supports_diffusion(state.model)
    rewrite_status = "ok"
    rewritten = message  # Default: pass through unchanged
    tokens_in = 0
    tokens_out = 0

    # --- Rate limiting ---
    if session_id:
        if not state.check_rate_limit(session_id):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: max {RATE_LIMIT_MAX_MESSAGES} messages per {int(RATE_LIMIT_WINDOW_SECONDS)} seconds. Please wait.",
            )

    # --- Token limit check ---
    if session_id and not state.check_token_limit(session_id):
        raise HTTPException(
            status_code=429,
            detail=f"Token limit exceeded: you have used your maximum allocation of {state.context_settings['max_tokens_per_user']} tokens.",
        )

    # Detect echo loops — if the user is feeding rewritten output back as input,
    # skip the rewrite to prevent recursive escalation
    is_echo = _is_echo_of_recent_rewrite(message)
    if is_echo:
        logger.info(f"Echo detected for {user} — skipping rewrite to prevent loop")
        rewrite_status = "passthrough"

    if is_echo:
        pass  # Already handled above — rewritten = message, status = passthrough
    elif use_diffusion:
        logger.info(f"Diffusion rewrite for {user}: {message[:80]}...")

        # Estimate input tokens for diffusion path
        from llm import build_rewrite_prompt
        system_prompt = build_rewrite_prompt(message, state.tone)
        tokens_in = estimate_tokens(system_prompt) + estimate_tokens(message)

        # Tell default room-tone clients a diffusion process is starting
        await broadcast_room_tone_only({
            "type": "diffusion_start",
            "msg_id": msg_id,
            "user": user,
            "original": message,
            "timestamp": timestamp,
            "tone_name": state.tone.tone_name,
        })

        # Stream real denoising steps from Mercury 2
        final_text = message
        step_count = 0

        async for denoised_state in rewrite_message_diffusion(message):
            final_text = denoised_state
            step_count += 1

            # Broadcast each intermediate state to default room-tone clients
            await broadcast_room_tone_only({
                "type": "diffusion_step",
                "msg_id": msg_id,
                "user": user,
                "content": denoised_state,
                "step": step_count,
                "timestamp": timestamp,
            })

        rewritten = final_text.strip().strip('"').strip("'") if final_text else message
        tokens_out = estimate_tokens(rewritten)
        logger.info(f"Diffusion done ({step_count} steps): {rewritten[:80]}...")

    else:
        # Standard (non-diffusion) rewrite
        logger.info(f"Standard rewrite for {user}: {message[:80]}...")
        result = await rewrite_message(message)
        rewritten = result["rewritten"]
        rewrite_status = result.get("rewrite_status", "ok")
        tokens_in = result.get("tokens_in", 0)
        tokens_out = result.get("tokens_out", 0)
        if rewrite_status != "ok":
            logger.warning(f"Rewrite status: {rewrite_status} — {result.get('error', '')}")
        logger.info(f"Rewritten: {rewritten[:80]}...")

    # --- Update token stats ---
    total_tokens = tokens_in + tokens_out
    if session_id:
        state.update_user_stats(session_id, total_tokens)
    else:
        # Still track global stats even without a session
        state.global_stats["total_messages"] += 1
        state.global_stats["total_tokens"] += total_tokens

    # Build final message record
    msg = ChatMessage(
        user=user,
        original=message,
        rewritten=rewritten,
        timestamp=timestamp,
        tone_name=state.tone.tone_name,
        tone_strength=state.tone.strength,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        tone_applied=state.tone.strength > 0,
        translation_language=None,
        source_language=_guess_language_name(message),
    )

    # Store
    state.add_message(msg.model_dump())

    # Broadcast the final resolved message, personalized per recipient
    await broadcast_chat_message(msg, msg_id, use_diffusion, rewrite_status, total_tokens)

    # Broadcast stats update after each message
    await broadcast({
        "type": "stats_update",
        "total_messages": state.global_stats["total_messages"],
        "total_tokens": state.global_stats["total_tokens"],
        "active_users": state.get_active_user_count(),
        "connected_clients": len(state.websocket_clients),
    })

    return msg

# ---------------------------------------------------------------------------
# Routes: Status
# ---------------------------------------------------------------------------

@app.get("/", response_model=StatusResponse)
async def get_status():
    return StatusResponse(
        connected_clients=len(state.websocket_clients),
        message_count=len(state.messages),
        tone=_tone_response(),
        model=_model_response(),
    )


# ---------------------------------------------------------------------------
# Routes: Auth / Session
# ---------------------------------------------------------------------------

@app.get("/auth/session")
async def get_session(request: Request):
    """
    Get current user session info. If no session exists, creates a new one.
    Always returns a session with the cookie set.
    """
    session_id, user, is_new = _get_or_create_session(request)

    response = JSONResponse(content=_session_response(user).model_dump())
    _set_session_cookie(response, session_id)
    return response


@app.post("/auth/join")
async def join_chat(req: JoinRequest, request: Request):
    """
    Join the chat with a username. Creates a new session or updates existing one.
    Returns session info with cookie set.
    """
    session_id = _get_session_id(request)
    is_new = False

    if session_id and session_id in state.users:
        # Update existing session's username
        user = state.users[session_id]
        user["username"] = req.username
        user["last_active"] = time.time()
        state.save_state()
    else:
        # Create new session
        session_id = str(uuid.uuid4())
        user = state.get_or_create_user(session_id, req.username)
        is_new = True

    response = JSONResponse(content=_session_response(user).model_dump())
    _set_session_cookie(response, session_id)

    # Broadcast user_joined event
    await broadcast({
        "type": "user_joined",
        "user_id": user["user_id"],
        "username": user["username"],
        "timestamp": time.time(),
        "user_count": state.get_active_user_count(),
    })

    logger.info(f"User joined: {req.username} (session={session_id[:8]}..., new={is_new})")
    return response


@app.post("/auth/admin")
async def admin_auth(req: AdminAuthRequest, request: Request):
    """
    Authenticate as admin. Checks password server-side.
    If correct, sets role='admin' on the current session.
    """
    session_id, user = _require_session(request)

    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid admin password.")

    user["role"] = "admin"
    state.save_state()
    logger.info(f"Admin authenticated: {user['username']} (session={session_id[:8]}...)")

    response = JSONResponse(content=_session_response(user).model_dump())
    _set_session_cookie(response, session_id)
    return response


@app.get("/preferences", response_model=PersonalizationResponse)
async def get_preferences(request: Request):
    """Get the current user's translation and tone preferences."""
    _, user = _require_session(request)
    return _personalization_response(user)


@app.post("/preferences", response_model=PersonalizationResponse)
async def update_preferences(req: UpdatePersonalizationRequest, request: Request):
    """Update the current user's translation and tone preferences."""
    _, user = _require_session(request)
    _update_user_preferences(user, req)
    return _personalization_response(user)


@app.get("/admin/personalization", response_model=PersonalizationAccessResponse)
async def get_personalization_access(request: Request):
    """Get admin-managed personalization access controls."""
    _require_admin(request)
    return _personalization_access_response()


@app.post("/admin/personalization", response_model=PersonalizationAccessResponse)
async def update_personalization_access(req: UpdatePersonalizationAccessRequest, request: Request):
    """Update admin-managed personalization access controls."""
    _require_admin(request)
    state.set_personalization(
        available_languages=req.available_languages,
        allow_user_tone_prompt_edit=req.allow_user_tone_prompt_edit,
        tone_prompt_presets=[preset.model_dump() for preset in req.tone_prompt_presets] if req.tone_prompt_presets is not None else None,
    )
    return _personalization_access_response()


# ---------------------------------------------------------------------------
# Routes: Chat
# ---------------------------------------------------------------------------

@app.post("/message", response_model=ChatMessage)
async def send_message(req: SendMessageRequest, request: Request):
    """Accept a chat message, rewrite it via LLM, broadcast to clients."""
    # Try to get session for tracking, but don't require it for backward compat
    session_id = _get_session_id(request)

    # If we have a session, update the username to match the request
    if session_id and session_id in state.users:
        state.users[session_id]["username"] = req.user
        state.users[session_id]["last_active"] = time.time()
        state.save_state()

    return await _process_message(req.user, req.message, session_id=session_id)


@app.get("/messages")
async def get_messages(request: Request, limit: int = 100):
    """Retrieve recent chat history personalized for the requesting user."""
    session_id = _get_session_id(request)
    user = state.get_user(session_id) if session_id else None
    signature = _user_transform_signature(user)

    history = state.get_messages(limit)
    if _is_default_transform_signature(signature):
        return history

    personalized = []
    for stored in history:
        base_msg = ChatMessage(**stored)
        payload = await _build_personalized_chat_payload(
            base_msg,
            str(uuid.uuid4())[:8],
            signature,
            use_diffusion=False,
            rewrite_status="ok",
            total_tokens=base_msg.tokens_in + base_msg.tokens_out,
        )
        personalized.append({
            "user": base_msg.user,
            "original": base_msg.original,
            "rewritten": payload["message"],
            "timestamp": base_msg.timestamp,
            "tone_name": payload["tone_name"],
            "token_estimate": payload["token_estimate"],
            "tone_applied": payload["tone_applied"],
            "translation_language": payload["translation_language"],
            "source_language": payload["source_language"],
        })
    return personalized


# ---------------------------------------------------------------------------
# Routes: Stats
# ---------------------------------------------------------------------------

@app.get("/stats", response_model=GlobalStatsResponse)
async def get_global_stats():
    """Return global stats: total messages, tokens, active users, per-user breakdown."""
    users_list = []
    for uid, u in state.users.items():
        state.sanitize_user_preferences(u)
        users_list.append(UserStatsResponse(
            user_id=uid,
            username=u["username"],
            role=u["role"],
            joined_at=u["joined_at"],
            last_active=u["last_active"],
            total_messages=u["total_messages"],
            total_tokens_used=u["total_tokens_used"],
            preferences=UserPreferences(**u["preferences"]),
        ))
    # Sort by total_messages descending
    users_list.sort(key=lambda u: u.total_messages, reverse=True)

    return GlobalStatsResponse(
        total_messages=state.global_stats["total_messages"],
        total_tokens=state.global_stats["total_tokens"],
        active_users=state.get_active_user_count(),
        total_users=len(state.users),
        connected_clients=len(state.websocket_clients),
        users=users_list,
    )


@app.get("/stats/me", response_model=MyStatsResponse)
async def get_my_stats(request: Request):
    """Return current user's stats. Requires a session cookie."""
    session_id, user = _require_session(request)

    return MyStatsResponse(
        user_id=user["user_id"],
        username=user["username"],
        role=user["role"],
        total_messages=user["total_messages"],
        total_tokens_used=user["total_tokens_used"],
        joined_at=user["joined_at"],
        last_active=user["last_active"],
        preferences=UserPreferences(**user["preferences"]),
    )

# ---------------------------------------------------------------------------
# Routes: Admin — Tone (protected)
# ---------------------------------------------------------------------------

@app.get("/admin/tone", response_model=ToneResponse)
async def get_tone():
    return _tone_response()


@app.post("/admin/tone", response_model=ToneResponse)
async def set_tone(req: SetToneRequest, request: Request):
    _require_admin(request)

    state.set_tone(
        tone_name=req.tone_name,
        description=req.description,
        strength=req.strength,
    )
    logger.info(f"Tone updated: {state.tone.tone_name} ({state.tone.strength}%)")

    await broadcast({
        "type": "tone_change",
        "tone_name": state.tone.tone_name,
        "description": state.tone.description,
        "strength": state.tone.strength,
    })

    return _tone_response()


@app.get("/admin/tone/presets", response_model=TonePresetsResponse)
async def get_tone_presets():
    return TonePresetsResponse(presets=TONE_PRESETS)


# ---------------------------------------------------------------------------
# Routes: Admin — Model (protected)
# ---------------------------------------------------------------------------

@app.get("/admin/model", response_model=ModelResponse)
async def get_model():
    return _model_response()


@app.post("/admin/model", response_model=ModelResponse)
async def set_model(req: SetModelRequest, request: Request):
    _require_admin(request)

    state.set_model(
        provider=req.provider,
        model=req.model,
        api_key=req.api_key,
        base_url=req.base_url,
        diffusion=req.diffusion,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        top_p=req.top_p,
        frequency_penalty=req.frequency_penalty,
        presence_penalty=req.presence_penalty,
        timeout=req.timeout,
    )
    logger.info(
        f"Model updated: {state.model.provider}/{state.model.model} "
        f"(diffusion={state.model.diffusion})"
    )
    return _model_response()


@app.get("/admin/model/presets", response_model=ProviderPresetsResponse)
async def get_provider_presets():
    return ProviderPresetsResponse(presets=PROVIDER_PRESETS)


# ---------------------------------------------------------------------------
# Routes: Admin — OpenRouter Model Search
# ---------------------------------------------------------------------------

# Simple in-memory cache for the OpenRouter model list
_openrouter_cache: dict = {"models": [], "fetched_at": 0.0}
_OPENROUTER_CACHE_TTL = 300.0  # 5 minutes


async def _fetch_openrouter_models() -> list[dict]:
    """Fetch and cache the OpenRouter model list."""
    now = time.time()
    if _openrouter_cache["models"] and (now - _openrouter_cache["fetched_at"]) < _OPENROUTER_CACHE_TTL:
        return _openrouter_cache["models"]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models")
            if resp.status_code != 200:
                logger.error(f"OpenRouter models API returned {resp.status_code}")
                return _openrouter_cache["models"]  # Return stale cache on error

            data = resp.json()
            models = []
            for m in data.get("data", []):
                pricing = m.get("pricing", {})
                prompt_price = pricing.get("prompt", "0")
                completion_price = pricing.get("completion", "0")

                models.append({
                    "id": m.get("id", ""),
                    "name": m.get("name", ""),
                    "context_length": m.get("context_length", 0),
                    "prompt_price": prompt_price,
                    "completion_price": completion_price,
                })

            _openrouter_cache["models"] = models
            _openrouter_cache["fetched_at"] = now
            logger.info(f"Fetched {len(models)} models from OpenRouter")
            return models

    except Exception as e:
        logger.error(f"Failed to fetch OpenRouter models: {e}")
        return _openrouter_cache["models"]


@app.get("/admin/openrouter/models")
async def search_openrouter_models(
    q: str = Query("", description="Search query to filter models by name or ID"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
):
    """
    Search available OpenRouter models. Returns a filtered, sorted list.
    Results are cached for 5 minutes.
    """
    all_models = await _fetch_openrouter_models()

    if q:
        q_lower = q.lower()
        filtered = [
            m for m in all_models
            if q_lower in m["id"].lower() or q_lower in m["name"].lower()
        ]
    else:
        filtered = all_models

    # Sort by name
    filtered.sort(key=lambda m: m["name"].lower())

    return {"models": filtered[:limit], "total": len(filtered)}


@app.get("/admin/openrouter/favorites")
async def get_openrouter_favorites():
    """
    Return curated list of recommended OpenRouter models for tone rewriting.
    These are hand-picked for being cheap, fast, and good at creative style transfer.
    """
    return {"favorites": OPENROUTER_FAVORITES}

# ---------------------------------------------------------------------------
# Routes: Admin — User Management (protected)
# ---------------------------------------------------------------------------

@app.post("/admin/users")
async def list_users(request: Request):
    """List all users with stats. Admin only."""
    _require_admin(request)

    users_list: list[UserSummaryResponse] = []
    for uid, u in state.users.items():
        state.sanitize_user_preferences(u)
        users_list.append(UserSummaryResponse(
            user_id=uid,
            username=u["username"],
            role=u["role"],
            joined_at=u["joined_at"],
            last_active=u["last_active"],
            total_messages=u["total_messages"],
            total_tokens_used=u["total_tokens_used"],
            preferences=UserPreferences(**u["preferences"]),
        ))

    # Sort by last_active descending
    users_list.sort(key=lambda u: u.last_active, reverse=True)
    return {"users": users_list, "total": len(users_list)}


@app.post("/admin/users/{user_id}/role")
async def set_user_role(user_id: str, req: SetRoleRequest, request: Request):
    """Set a user's role. Admin only."""
    _require_admin(request)

    user = state.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user["role"] = req.role
    state.save_state()
    logger.info(f"User role updated: {user['username']} -> {req.role}")
    return {"status": "ok", "user_id": user_id, "role": req.role}


@app.post("/admin/users/{user_id}/kick")
async def kick_user(user_id: str, request: Request):
    """Remove a user's session (kick them). Admin only."""
    admin_session_id, admin_user = _require_admin(request)

    if user_id == admin_session_id:
        raise HTTPException(status_code=400, detail="Cannot kick yourself.")

    target_user = state.get_user(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    username = target_user["username"]
    state.remove_user(user_id)

    # Broadcast user_left event
    await broadcast({
        "type": "user_left",
        "user_id": user_id,
        "username": username,
        "reason": "kicked",
        "timestamp": time.time(),
        "user_count": state.get_active_user_count(),
    })

    logger.info(f"User kicked: {username} (session={user_id[:8]}...)")
    return {"status": "ok", "user_id": user_id, "username": username}


# ---------------------------------------------------------------------------
# Routes: Admin — Context Management (protected)
# ---------------------------------------------------------------------------

@app.get("/admin/context")
async def get_context_stats(request: Request):
    """Get current context stats. Admin only."""
    _require_admin(request)

    return ContextStatsResponse(
        message_count=len(state.messages),
        total_tokens=state.global_stats["total_tokens"],
        max_messages=state.context_settings["max_messages"],
        max_tokens_per_user=state.context_settings["max_tokens_per_user"],
    )


@app.post("/admin/context/reset")
async def reset_context(request: Request):
    """Clear all messages. Admin only."""
    _require_admin(request)

    msg_count = len(state.messages)
    state.messages.clear()
    state.save_state()
    logger.info(f"Context reset by admin: {msg_count} messages cleared")

    # Broadcast context_reset event
    await broadcast({
        "type": "context_reset",
        "timestamp": time.time(),
        "cleared_messages": msg_count,
    })

    return {"status": "ok", "cleared_messages": msg_count}


@app.post("/admin/context/settings")
async def update_context_settings(req: ContextSettingsRequest, request: Request):
    """Update context limits (max_messages, max_tokens_per_user). Admin only."""
    _require_admin(request)

    if req.max_messages is not None:
        state.context_settings["max_messages"] = req.max_messages
        # Enforce the new limit immediately if we have too many messages
        if len(state.messages) > req.max_messages:
            overflow = len(state.messages) - req.max_messages
            state.messages = state.messages[overflow:]
            logger.info(f"Trimmed {overflow} messages to meet new max_messages={req.max_messages}")

    if req.max_tokens_per_user is not None:
        state.context_settings["max_tokens_per_user"] = req.max_tokens_per_user

    logger.info(f"Context settings updated: {state.context_settings}")
    state.save_state()

    return {
        "status": "ok",
        "max_messages": state.context_settings["max_messages"],
        "max_tokens_per_user": state.context_settings["max_tokens_per_user"],
    }

# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    state.websocket_clients.append(websocket)
    logger.info(f"WebSocket client connected ({len(state.websocket_clients)} total)")

    # Try to extract session from cookies for WS tracking
    ws_session_id = websocket.cookies.get(SESSION_COOKIE_NAME)
    ws_user = None
    if ws_session_id:
        ws_user = state.get_user(ws_session_id)
        if ws_user:
            ws_user["last_active"] = time.time()
            logger.info(f"WebSocket identified user: {ws_user['username']} (session={ws_session_id[:8]}...)")
    state.websocket_sessions[id(websocket)] = ws_session_id

    try:
        while True:
            data = await websocket.receive_text()

            try:
                parsed = json.loads(data)
                if parsed.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif parsed.get("type") == "message":
                    user = parsed.get("user", "Anonymous")
                    message = parsed.get("message", "")
                    if message:
                        # Use the WS session for tracking if available
                        try:
                            await _process_message(user, message, session_id=ws_session_id)
                        except HTTPException as e:
                            # Send rate limit / token limit errors back to the WS client
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "code": e.status_code,
                                "detail": e.detail,
                            }))
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        pass
    finally:
        if websocket in state.websocket_clients:
            state.websocket_clients.remove(websocket)
        state.websocket_sessions.pop(id(websocket), None)

        # Broadcast user_left if we had a tracked session
        if ws_user:
            await broadcast({
                "type": "user_left",
                "user_id": ws_session_id,
                "username": ws_user.get("username", "Unknown"),
                "reason": "disconnected",
                "timestamp": time.time(),
                "user_count": state.get_active_user_count(),
            })

        logger.info(f"WebSocket client disconnected ({len(state.websocket_clients)} total)")


# ---------------------------------------------------------------------------
# Run with: uvicorn main:app --reload --port 8000
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
