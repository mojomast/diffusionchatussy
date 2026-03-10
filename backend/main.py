"""
Tone-Field Chat — FastAPI Backend

Single-file server with:
- REST endpoints for chat, admin tone, admin model config
- WebSocket endpoint for realtime message broadcasting
- Real diffusion streaming: Mercury 2 denoising steps broadcast live to clients
- CORS middleware for local frontend dev
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import state, PROVIDER_PRESETS, TONE_PRESETS
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
)
from llm import rewrite_message, rewrite_message_diffusion, supports_diffusion

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("tonechat")


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
    yield
    logger.info("ToneChat backend shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ToneChat",
    description="Tone-Field Chat — messages rewritten by LLM to match a tone profile",
    version="0.2.0",
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


# ---------------------------------------------------------------------------
# Core: process a message (with or without diffusion streaming)
# ---------------------------------------------------------------------------

async def _process_message(user: str, message: str) -> ChatMessage:
    """
    Process a chat message through the rewrite pipeline.

    If diffusion is enabled and the provider supports it:
      1. Broadcast a `diffusion_start` event
      2. Stream each denoising step as `diffusion_step` events
      3. Broadcast the final `chat` event

    Otherwise: standard rewrite + broadcast.
    """

    timestamp = time.time()
    msg_id = str(uuid.uuid4())[:8]
    use_diffusion = state.model.diffusion and supports_diffusion(state.model)
    rewrite_status = "ok"

    if use_diffusion:
        logger.info(f"Diffusion rewrite for {user}: {message[:80]}...")

        # Tell clients a diffusion process is starting
        await broadcast({
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

            # Broadcast each intermediate state to all clients
            await broadcast({
                "type": "diffusion_step",
                "msg_id": msg_id,
                "user": user,
                "content": denoised_state,
                "step": step_count,
                "timestamp": timestamp,
            })

        rewritten = final_text.strip().strip('"').strip("'") if final_text else message
        logger.info(f"Diffusion done ({step_count} steps): {rewritten[:80]}...")

    else:
        # Standard (non-diffusion) rewrite
        logger.info(f"Standard rewrite for {user}: {message[:80]}...")
        result = await rewrite_message(message)
        rewritten = result["rewritten"]
        rewrite_status = result.get("rewrite_status", "ok")
        if rewrite_status != "ok":
            logger.warning(f"Rewrite status: {rewrite_status} — {result.get('error', '')}")
        logger.info(f"Rewritten: {rewritten[:80]}...")

    # Build final message record
    msg = ChatMessage(
        user=user,
        original=message,
        rewritten=rewritten,
        timestamp=timestamp,
        tone_name=state.tone.tone_name,
        tone_strength=state.tone.strength,
    )

    # Store
    state.add_message(msg.model_dump())

    # Broadcast the final resolved message
    await broadcast({
        "type": "chat",
        "msg_id": msg_id,
        "user": msg.user,
        "message": msg.rewritten,
        "original": msg.original,
        "timestamp": msg.timestamp,
        "tone_name": msg.tone_name,
        "diffused": use_diffusion,
        "rewrite_status": rewrite_status if not use_diffusion else "ok",
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
# Routes: Chat
# ---------------------------------------------------------------------------

@app.post("/message", response_model=ChatMessage)
async def send_message(req: SendMessageRequest):
    """Accept a chat message, rewrite it via LLM, broadcast to clients."""
    return await _process_message(req.user, req.message)


@app.get("/messages")
async def get_messages(limit: int = 100):
    """Retrieve recent chat history."""
    return state.get_messages(limit)


# ---------------------------------------------------------------------------
# Routes: Admin — Tone
# ---------------------------------------------------------------------------

@app.get("/admin/tone", response_model=ToneResponse)
async def get_tone():
    return _tone_response()


@app.post("/admin/tone", response_model=ToneResponse)
async def set_tone(req: SetToneRequest):
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
# Routes: Admin — Model
# ---------------------------------------------------------------------------

@app.get("/admin/model", response_model=ModelResponse)
async def get_model():
    return _model_response()


@app.post("/admin/model", response_model=ModelResponse)
async def set_model(req: SetModelRequest):
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
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    state.websocket_clients.append(websocket)
    logger.info(f"WebSocket client connected ({len(state.websocket_clients)} total)")

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
                        await _process_message(user, message)
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        pass
    finally:
        if websocket in state.websocket_clients:
            state.websocket_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected ({len(state.websocket_clients)} total)")


# ---------------------------------------------------------------------------
# Run with: uvicorn main:app --reload --port 8000
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
