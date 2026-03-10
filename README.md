# DiffusionChat

A chat system where every message is rewritten by an LLM to match the room's tone — and when you use Mercury 2 (the first diffusion LLM), you watch the real denoising process happen live. Text resolves from noise into the room's vibe through the model's actual diffusion steps, streamed to your screen in realtime.

Not a simulation. Not an animation. The actual model internals, piped to your chat window.

## How It Works

```
User types message
       |
       v
Backend sends to Mercury 2 with tone instructions
       |
       v
Mercury 2 diffuses: parallel token refinement, coarse → fine
       |
       v
Each denoising step is streamed over WebSocket to all clients
       |
       v
Chat shows text resolving from noise → coherent tone-shifted message
```

With diffusion OFF (or using a non-diffusion model like GPT-4o-mini), messages are rewritten normally — you just see the final result. With diffusion ON using Mercury 2 via the Inception API, you see the intermediate states as the model refines the output.

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- An API key (Inception for diffusion, or OpenRouter/OpenAI/etc for standard mode)

### 1. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Optional: set API key via env (can also set in admin UI)
export LLM_API_KEY="your-key-here"

# Start the server
python main.py
```

Backend runs at `http://localhost:8000`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`, proxies API calls to the backend.

### 3. Configure

1. Open `http://localhost:5173`, enter a name
2. Click **Admin** in the top right
3. Set your provider and API key:
   - For **real diffusion**: select `inception` provider, model `mercury-2`, enter your Inception API key, and check "Real diffusion streaming"
   - For **standard mode**: select `openrouter` or any other provider
4. Pick a tone, set strength, hit Apply
5. Chat. Watch your words transform.

## Real Diffusion Streaming

This is the core feature. Mercury 2 by Inception is a discrete diffusion LLM — instead of generating tokens one at a time left-to-right (autoregressive), it refines the entire output in parallel through denoising steps: noise → rough draft → refined → final.

Mercury 2's API exposes these intermediate states via `"stream": true, "diffusing": true`. DiffusionChat pipes them directly to the frontend over WebSocket:

1. Backend receives your message
2. Calls Mercury 2 with `diffusing: true`
3. Each SSE chunk contains the **full current denoised state** (not incremental tokens)
4. Backend broadcasts each state as a `diffusion_step` WebSocket event
5. Frontend renders each step in place — you watch text resolve from noise
6. Final `chat` event replaces the diffusing message with the resolved result

The WebSocket message flow:

```json
{"type": "diffusion_start", "msg_id": "a1b2c3", "user": "Kyle", "original": "this sucks"}
{"type": "diffusion_step",  "msg_id": "a1b2c3", "content": "th$s ne#ds imp@ov!ment", "step": 1}
{"type": "diffusion_step",  "msg_id": "a1b2c3", "content": "this needs improvement.", "step": 2}
{"type": "diffusion_step",  "msg_id": "a1b2c3", "content": "This could use some improvement.", "step": 3}
{"type": "chat",            "msg_id": "a1b2c3", "message": "This could use some improvement.", "diffused": true}
```

## Supported Providers

| Provider | Base URL | Default Model | Diffusion |
|---|---|---|---|
| **inception** | `https://api.inceptionlabs.ai/v1` | `mercury-2` | Yes — real denoising steps |
| **openrouter** | `https://openrouter.ai/api/v1` | `inception/mercury-2` | No — standard completion |
| openai | `https://api.openai.com/v1` | `gpt-4o-mini` | No |
| anthropic | `https://api.anthropic.com/v1` | `claude-3-5-sonnet-20241022` | No |
| together | `https://api.together.xyz/v1` | `meta-llama/Llama-3-70b-chat-hf` | No |
| groq | `https://api.groq.com/openai/v1` | `llama-3.1-70b-versatile` | No |
| local | `http://localhost:1234/v1` | Any local model | No |
| custom | (you set it) | (you set it) | No |

All providers use the OpenAI-compatible chat completions format. Real diffusion streaming is only available via the Inception API directly (the `"diffusing"` param is Inception-specific).

## Mercury 2

[Mercury 2](https://www.inceptionlabs.ai/blog/introducing-mercury-2) is the first commercial reasoning diffusion LLM:

- **1,000+ tokens/sec** on NVIDIA GPUs — 5-10x faster than GPT-4o-mini or Claude 3.5 Haiku
- **$0.25/M input, $0.75/M output tokens** — ~$0.00004 per chat rewrite
- **128K context**, native tool use, structured JSON output
- **OpenAI-compatible API** — drop-in replacement
- **10M free tokens** on signup at [platform.inceptionlabs.ai](https://platform.inceptionlabs.ai)

## Model Configuration

All tunable from the admin panel or API:

| Parameter | Range | Default | Description |
|---|---|---|---|
| `diffusion` | true/false | false | Stream real denoising steps (Inception only) |
| `max_tokens` | 1–4096 | 256 | Max tokens in the rewrite |
| `temperature` | 0.0–2.0 | 0.7 | Sampling randomness |
| `top_p` | 0.0–1.0 | 1.0 | Nucleus sampling |
| `frequency_penalty` | -2.0–2.0 | 0.0 | Repeated token penalty |
| `presence_penalty` | -2.0–2.0 | 0.0 | Already-present token penalty |
| `timeout` | 1–120s | 30 | Request timeout |

## Tone Presets

- **friendly** — Casual, polite, collaborative
- **professional** — Formal, clear, respectful
- **sarcastic** — Witty, not mean-spirited
- **academic** — Calm, analytical, scholarly
- **chaotic** — Unpredictable, playful, energetic
- **supportive** — Encouraging, empathetic, kind
- **concise** — Extremely brief, no fluff
- **poetic** — Lyrical, metaphorical, expressive

Plus a strength slider: 0% (raw passthrough) to 100% (full tone rewrite). Custom tone descriptions supported.

## API Reference

### Chat

```
POST /message    { "user": "Kyle", "message": "this code is trash" }
GET  /messages   ?limit=100
```

### Tone

```
GET  /admin/tone
POST /admin/tone          { "tone_name": "academic", "description": "...", "strength": 80 }
GET  /admin/tone/presets
```

### Model

```
GET  /admin/model
POST /admin/model         { "provider": "inception", "model": "mercury-2", "diffusion": true, ... }
GET  /admin/model/presets
```

### WebSocket

```
ws://localhost:8000/ws/chat
```

Message types: `diffusion_start`, `diffusion_step`, `chat`, `tone_change`, `pong`

## Project Structure

```
diffusionchat/
  backend/
    main.py            # FastAPI app, routes, WebSocket, diffusion streaming
    config.py          # App state, tone/model config, provider presets
    llm.py             # LLM client: standard + diffusion streaming (Mercury 2)
    models.py          # Pydantic request/response schemas
    requirements.txt
  frontend/
    src/
      components/
        Chat.tsx          # Chat window, diffusing message display, pipeline status
        AdminPanel.tsx    # Tone, model, diffusion toggle, advanced settings
        DiffusionText.tsx # Renders real denoising step content
      hooks/
        useWebSocket.ts   # WebSocket with auto-reconnect
      types/
        index.ts          # TypeScript types (WSMessage union, DiffusingMessage, etc)
      api.ts              # HTTP API client
      App.tsx             # State management, WS message routing
      main.tsx
      index.css
    index.html
    package.json
    vite.config.ts
    tailwind.config.js
    tsconfig.json
  .env.example
  .gitignore
  README.md
```

## Cost

Mercury 2: $0.25/M input, $0.75/M output. At ~50 tokens per rewrite, that's ~25,000 rewrites per dollar. Free tier: 10M tokens on signup.

## License

MIT
