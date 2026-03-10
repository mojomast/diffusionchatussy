# Handoff: DiffusionChat

## What this is

A chat app where every message gets rewritten by an LLM to match a room-wide tone profile. The admin controls the tone (friendly, sarcastic, academic, etc.) and all messages drift toward it.

Built in one session. Works. Has some unfinished ideas that need attention.

## Status: What works right now

- **Full chat system**: username entry → chat room → realtime WebSocket broadcasting
- **Tone rewriting**: messages sent via POST → rewritten by LLM → broadcast to all clients
- **Admin panel**: tone presets + custom, strength slider (0-100%), model/provider config with full parameter control
- **8 provider presets**: Inception, OpenRouter, OpenAI, Anthropic, Together, Groq, local, custom
- **Mercury 2 diffusion streaming**: `diffusing: true` param → SSE → WebSocket `diffusion_step` events → frontend renders each denoising state
- **Frontend builds clean**: TypeScript strict, Vite production build passes
- **Backend parses clean**: all 4 Python files, FastAPI with Pydantic v2

## The big unresolved thing

### The diffusion isn't doing what was originally envisioned

The original idea (from the chat log that inspired this project) was:

```
user types message
        ↓
the USER'S TEXT is the starting noise
        ↓
diffusion refinement toward tone target
        ↓
posted message
```

Like img2img in Stable Diffusion — your raw input IS the noisy sample, and the model denoises it toward the target distribution (the tone). Your words literally morph into the toned version.

**What's actually built** is different. Mercury 2's `diffusing: true` API mode shows the denoising of the **output generation** — it starts from random noise and refines toward the answer. The user's message goes in as prompt context, not as the noise seed. It's output-side diffusion visualization, not input-to-output transformation.

```
CURRENT:
  prompt: "rewrite X in friendly tone"  →  Mercury 2 starts from RANDOM NOISE  →  denoises to answer

ENVISIONED:
  "this code is garbage"  →  IS the noisy starting point  →  denoises toward tone  →  "this code could use work"
```

Nobody offers the second thing as an API yet. Mercury 2 doesn't have an "init_text" or "denoising_strength" parameter analogous to img2img.

### Possible paths forward

1. **Multi-pass iterative refinement**: Make N calls with escalating tone strength (10% → 40% → 70% → 100%), streaming each intermediate to the frontend. Not real diffusion, but actually morphs the user's original words step-by-step. Closest to the dream-staircase idea. Mercury 2 is fast enough (1000+ tok/s) to make 3-4 passes feel instant.

2. **Prompt-engineered pseudo-diffusion**: One call, but prompt the LLM to output multiple intermediate versions:
   ```
   Step 1 (slight adjustment): "this code is kinda garbage"
   Step 2 (moderate): "this code needs some work"
   Step 3 (full tone): "this code could use some improvement"
   ```
   Parse and stream each step. Hacky but fast.

3. **Wait for APIs to catch up**: If Inception or someone else adds an init_text parameter for text-to-text diffusion refinement, wire it in. The WebSocket infrastructure for streaming steps already exists.

4. **Build your own**: If you want the real deal, you'd need to run a discrete diffusion model locally and implement the text-to-text noising/denoising pipeline yourself. Heavy lift.

Option 1 is probably the right next step. The infrastructure to stream multiple steps to the frontend over WebSocket is already built and tested.

## Architecture

```
Browser (React/TS/Vite)
   │
   │ HTTP POST /message
   │ WebSocket /ws/chat
   ▼
FastAPI Backend (Python)
   │
   │ httpx → OpenAI-compatible chat completions
   │ (optionally with stream=true, diffusing=true for Mercury 2)
   ▼
LLM Provider (Inception / OpenRouter / OpenAI / etc)
```

### Backend (backend/)

| File | What it does |
|---|---|
| `config.py` | AppState singleton, ToneConfig, ModelConfig, PROVIDER_PRESETS, TONE_PRESETS. All in-memory. |
| `llm.py` | `build_rewrite_prompt()`, `call_llm()` (standard), `call_llm_diffusion()` (async generator yielding SSE states), `rewrite_message()`, `rewrite_message_diffusion()`, `supports_diffusion()` |
| `main.py` | FastAPI app. `_process_message()` is the core — routes to diffusion or standard path, broadcasts WS events. Routes for /message, /admin/tone, /admin/model, /ws/chat. |
| `models.py` | Pydantic v2 request/response schemas. |

### Frontend (frontend/src/)

| File | What it does |
|---|---|
| `types/index.ts` | `WSMessage` discriminated union (chat, diffusion_start, diffusion_step, tone_change, pong). `DiffusingMessage` for in-flight tracking. |
| `App.tsx` | Main state. Manages `messages: ChatMessage[]` (resolved) and `diffusing: Map<string, DiffusingMessage>` (in-flight). Routes WS events. |
| `components/Chat.tsx` | Renders resolved messages + in-flight diffusing messages. Pipeline status indicator. |
| `components/DiffusionText.tsx` | Dead simple — renders `content` string + animated cursor when active. |
| `components/AdminPanel.tsx` | Tone presets/custom, strength slider, provider dropdown, model config, diffusion toggle with warning if provider doesn't support it, advanced params. |
| `hooks/useWebSocket.ts` | Auto-reconnecting WS with `onMessage` callback ref pattern. |
| `api.ts` | Typed HTTP client for all REST endpoints. |

### WebSocket message flow (diffusion mode)

```
Server → Client:  { type: "diffusion_start", msg_id, user, original, timestamp, tone_name }
Server → Client:  { type: "diffusion_step",  msg_id, content: "full denoised state", step: 1 }
Server → Client:  { type: "diffusion_step",  msg_id, content: "more refined state",  step: 2 }
...
Server → Client:  { type: "chat", msg_id, user, message: "final", original, diffused: true }
```

Frontend tracks in-flight messages by `msg_id`. When `chat` arrives, removes from `diffusing` map and adds to `messages` array.

### WebSocket message flow (standard mode)

```
Server → Client:  { type: "chat", user, message: "rewritten", original, diffused: false }
```

## How to run

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export LLM_API_KEY="your-key"   # or set via admin UI
python main.py                   # runs on :8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                      # runs on :5173, proxies /api → :8000
```

### Config for real diffusion testing

In the admin panel:
- Provider: `inception`
- Model: `mercury-2`
- API Key: get from platform.inceptionlabs.ai (10M free tokens)
- Check "Real diffusion streaming"
- Apply

### Config for standard testing (no diffusion)

- Provider: `openrouter`
- Model: `inception/mercury-2` (or `deepseek/deepseek-chat`, whatever)
- API Key: your OpenRouter key
- Leave diffusion unchecked

## Known issues / things to clean up

1. **The diffusion visualization is output-side, not input-side** — see "big unresolved thing" above
2. **No auth** — admin panel is accessible to everyone. Fine for PoC, not for prod.
3. **In-memory only** — messages and config vanish on restart. Add SQLite or Redis if you need persistence.
4. **No rate limiting** — every message = one LLM call. Easy to burn tokens.
5. **Anthropic provider** — listed in presets but Anthropic's API isn't fully OpenAI-compatible (different message format for system prompts). Might need special handling.
6. **Error display** — backend errors are logged server-side but the frontend just silently falls back. Could surface errors in the UI.
7. **Multi-user testing** — WebSocket broadcast works but hasn't been stress-tested with many concurrent users.

## Deps

Backend: `fastapi`, `uvicorn`, `pydantic`, `httpx`, `websockets`, `python-dotenv`
Frontend: `react`, `react-dom`, `vite`, `tailwindcss`, `typescript`

## Repo

https://github.com/mojomast/diffusionchatussy
