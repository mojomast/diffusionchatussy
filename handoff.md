# Handoff: ToneChat (DiffusionChat)

## What this is

A chat app where every message gets rewritten by an LLM to match a room-wide tone profile. The admin controls the tone (friendly, sarcastic, academic, poetic, etc.) and all messages drift toward it. Users type raw messages, the backend rewrites them via an LLM API call, and the rewritten version is broadcast to all connected clients over WebSocket.

Built across three sessions. Session 1 built the core app. Session 2 fixed bugs from real user testing and added the OpenRouter model browser. Session 3 added user management, auth, token tracking, context management, and rate limiting.

## Status: What works right now

- **Full chat system**: username entry -> cookie-based session -> chat room -> realtime WebSocket broadcasting
- **Tone rewriting**: messages sent via POST -> rewritten by LLM -> broadcast to all clients
- **Admin panel**: tone presets + custom, strength slider (0-100%), model/provider config with full parameter control
- **8 provider presets**: Inception, OpenRouter, OpenAI, Anthropic, Together, Groq, local, custom
- **OpenRouter model browser**: searchable list of 346+ models with 10 curated favorites for tone rewriting
- **Mercury 2 diffusion streaming**: `diffusing: true` param -> SSE -> WebSocket `diffusion_step` events -> frontend renders each denoising state
- **Refusal detection**: LLM safety filter responses are caught and the original message is shown instead
- **Echo loop prevention**: copy-pasting a rewritten message back as input is detected and short-circuited
- **Prompt injection resistance**: system prompt explicitly tells the LLM to ignore embedded instructions
- **Cookie-based user sessions**: persistent UUID session cookies, server-side user tracking
- **Server-side admin auth**: password verified on backend, role-based access control
- **Token tracking**: per-user and global token/message counts, live stats in UI
- **Context management**: configurable message limits, per-user token limits, admin can reset chat history
- **Rate limiting**: 10 messages per user per 60 seconds, returns 429
- **User management**: admin can list users, change roles, kick users
- **Live stats**: real-time message count, token count, and user count in header and chat
- **System messages**: join/leave/reset notifications displayed inline in chat
- **Frontend builds clean**: TypeScript strict, Vite production build passes
- **Backend parses clean**: all 4 Python files, FastAPI with Pydantic v2

## What was added in session 3

### Cookie-based user sessions

**Problem**: No user identity. Anyone could impersonate anyone. No way to track who's using how many tokens.

**Fix**: When a user clicks "Join Chat", the frontend calls `POST /auth/join` with their username. The backend creates a UUID4 session, stores user info in memory (`state.users`), and sets an httponly `tonechat_session` cookie (30-day expiry, samesite=lax). All subsequent requests include the cookie automatically via `credentials: "include"` on every fetch call.

Key files: `backend/main.py:115-177` (session helpers), `frontend/src/api.ts:7-21` (credentials include), `frontend/src/App.tsx:226-243` (join flow).

### Server-side admin auth

**Problem**: Admin password was client-side only (`"h4x0r"` in App.tsx). Anyone could hit `/admin/tone` or `/admin/model` directly.

**Fix**: `POST /auth/admin` checks the password server-side (configurable via `ADMIN_PASSWORD` env var, defaults to `"h4x0r"`). On success, sets `role="admin"` on the user's session. All mutating `/admin/*` endpoints now call `_require_admin()` which checks the session cookie for `role == "admin"`. GET endpoints for tone/model remain public for backward compatibility.

Key files: `backend/main.py:168-177` (_require_admin), `backend/main.py:489-505` (admin auth endpoint), `backend/config.py:22` (ADMIN_PASSWORD).

### Token tracking

**Problem**: No visibility into how many tokens are being consumed. Chat could burn through API credits silently.

**Fix**: `estimate_tokens()` in `llm.py` uses a simple heuristic: `max(1, int(len(text.split()) * 1.3))`. Every LLM call tracks input tokens (system prompt + user message) and output tokens (rewritten text). Per-user and global stats are updated after every message. The frontend shows:
- Live stats bar in header: total messages, total tokens, users online
- Per-message token estimate next to timestamp
- Personal stats in settings sidebar
- `stats_update` WS events keep everything in sync

Key files: `backend/llm.py:31-36` (estimate_tokens), `backend/main.py:374-381` (stat updates), `frontend/src/components/Chat.tsx:103-118` (stats bar).

### Context management

**Problem**: In-memory message list grows unbounded. Frontend slows down with hundreds of DOM nodes. No way to clear history.

**Fix**: `max_messages` (default 500) in `state.context_settings`. When exceeded, `add_message()` trims the oldest messages. `max_tokens_per_user` (default 100,000) prevents any single user from burning through the token budget. Admin panel has:
- Progress bar showing messages used vs limit
- Sliders for max_messages (50-2000) and max_tokens_per_user (10k-500k)
- "Reset Chat History" button with confirmation — clears all messages and broadcasts `context_reset` WS event
- All limits adjustable live without restart

Key files: `backend/config.py:317-324` (add_message trim), `backend/main.py:805-859` (context endpoints), `frontend/src/components/AdminPanel.tsx` (context management section).

### Rate limiting

**Problem**: Every message = one LLM call. Easy to burn tokens with rapid-fire messages.

**Fix**: In-memory rate limiter: max 10 messages per user per 60 seconds. Checked before the LLM call in `_process_message()`. Returns HTTP 429 with a clear error message. WebSocket messages are also rate-limited, with errors sent back as `{type: "error", code: 429, detail: "..."}`.

Key files: `backend/config.py:147-148` (rate limit config), `backend/config.py:331-353` (check_rate_limit), `backend/main.py:299-304` (enforcement).

### User management

**Problem**: No way to see who's connected, manage privileges, or remove bad actors.

**Fix**: Admin panel now has a "Users" section showing all tracked users with: username, role badge, messages sent, tokens used, last active time. For each user, admin can change role (user/admin dropdown) or kick them. Auto-refreshes every 10 seconds.

Key files: `backend/main.py:737-798` (user management endpoints), `frontend/src/components/AdminPanel.tsx` (user management section).

### System messages & display improvements

**Problem**: No visibility when users join/leave or when admin actions happen.

**Fix**: New `DisplayMessage` union type combines chat messages and system messages. System messages (centered, rounded pill, gray) show for: user joined, user left, chat history cleared. The chat component renders both types in chronological order.

Key files: `frontend/src/types/index.ts:86-93` (DisplayMessage type), `frontend/src/App.tsx:56-64` (addSystemMessage), `frontend/src/components/Chat.tsx:130-141` (system message rendering).

## Architecture

```
Browser (React/TS/Vite)
   |
   | HTTP POST /message (with session cookie)
   | HTTP POST /auth/join, /auth/admin
   | HTTP GET /stats, /stats/me
   | WebSocket /ws/chat (cookie extracted for tracking)
   v
FastAPI Backend (Python)
   |
   | Session management (in-memory, cookie-based)
   | Rate limiting (10 msgs/60s per user)
   | Token tracking (per-user + global)
   | httpx -> OpenAI-compatible chat completions
   | (optionally with stream=true, diffusing=true for Mercury 2)
   v
LLM Provider (Inception / OpenRouter / OpenAI / etc)
```

### Backend (backend/)

| File | Lines | What it does |
|---|---|---|
| `config.py` | 418 | AppState singleton, ToneConfig, ModelConfig, PROVIDER_PRESETS, TONE_PRESETS, OPENROUTER_FAVORITES, ADMIN_PASSWORD, user session management, rate limiting, token tracking, context settings. All in-memory. |
| `llm.py` | 427 | `estimate_tokens()`, `build_rewrite_prompt()`, `_is_refusal()`, `call_llm()` (standard), `call_llm_diffusion()` (async generator yielding SSE states), `rewrite_message()` (now returns tokens_in/tokens_out), `rewrite_message_diffusion()`, `supports_diffusion()` |
| `main.py` | 930 | FastAPI app. Session helpers, admin auth, rate limiting, token tracking. Routes for /auth/*, /message, /stats/*, /admin/tone, /admin/model, /admin/openrouter/*, /admin/users/*, /admin/context/*, /ws/chat. `_process_message()` is the core with rate limit + token limit checks. |
| `models.py` | 192 | Pydantic v2 request/response schemas including auth, stats, user management, and context management models. |

### Frontend (frontend/src/)

| File | Lines | What it does |
|---|---|---|
| `types/index.ts` | 188 | All types: ChatMessage (with token_estimate), UserSession, StatsResponse, MyStatsResponse, ContextStats, SystemMessage, DisplayMessage union, WSMessage discriminated union (chat, diffusion_start, diffusion_step, tone_change, pong, context_reset, user_joined, user_left, stats_update), DiffusingMessage. |
| `App.tsx` | 543 | Main state. Session management via /auth/join and /auth/admin. Handles all WS events including new ones. Live stats, personal stats, system messages. Admin password verified server-side. |
| `components/Chat.tsx` | 314 | Renders display messages (chat + system) + diffusing messages. Stats bar, auto-scroll, auto-focus, pipeline status, per-message token estimates. |
| `components/AdminPanel.tsx` | ~850 | Tone presets/custom, strength slider, provider dropdown, model config, OpenRouter model browser, diffusion toggle, advanced params. NEW: Context management (stats, limits, reset), User management (list, roles, kick). |
| `components/DiffusionText.tsx` | 28 | Renders `content` string + animated cursor when active. |
| `hooks/useWebSocket.ts` | 61 | Auto-reconnecting WS with `onMessage` callback ref pattern. |
| `api.ts` | 232 | Typed HTTP client with `credentials: "include"` for all calls. All REST endpoints including auth, stats, user management, context management, OpenRouter model search. |

## Message processing pipeline

```
User sends POST /message { user, message } (with session cookie)
          |
          v
    _process_message()
          |
    1. Generate msg_id (UUID[:8]) and timestamp
    2. Rate limit check (10 msgs / 60s per session) -> 429 if exceeded
    3. Token limit check (per-user max) -> 429 if exceeded
    4. Check _is_echo_of_recent_rewrite()
       - If echo: passthrough (no LLM call), skip to step 8
          |
    5. Is diffusion enabled + supported?
       |                          |
       YES                        NO
       |                          |
    6a. broadcast                6b. call rewrite_message()
        diffusion_start              - build_rewrite_prompt()
        |                            - call_llm() via httpx
        for each SSE chunk:          - _is_refusal() check
          broadcast                  - estimate tokens in/out
          diffusion_step             - return rewritten or original
        |                            |
    7. Strip quotes              7. Check rewrite_status
          |                          |
          v                          v
    8. Update user stats (tokens, message count)
    9. Store ChatMessage in state.messages (auto-trim if > max_messages)
   10. Broadcast { type: "chat", ..., token_estimate } to all WS clients
   11. Broadcast { type: "stats_update", ... } to all WS clients
```

### WebSocket message types

| Type | Direction | Purpose |
|---|---|---|
| `diffusion_start` | Server -> Client | New message entering diffusion pipeline |
| `diffusion_step` | Server -> Client | Intermediate denoised state (full text, not delta) |
| `chat` | Server -> Client | Final resolved message (now includes token_estimate) |
| `tone_change` | Server -> Client | Admin changed the tone |
| `context_reset` | Server -> Client | Admin cleared all messages |
| `user_joined` | Server -> Client | A user joined the chat |
| `user_left` | Server -> Client | A user left or was kicked |
| `stats_update` | Server -> Client | Updated global stats (after each message) |
| `error` | Server -> Client | Rate limit or token limit error (WS only) |
| `pong` | Server -> Client | Keepalive response |
| `ping` | Client -> Server | Keepalive |

### API endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/` | none | Status (clients, messages, tone, model) |
| `POST` | `/message` | cookie (optional) | Send a chat message |
| `GET` | `/messages` | none | Get recent message history |
| `GET` | `/auth/session` | none | Get or create session |
| `POST` | `/auth/join` | none | Join chat with username, get session cookie |
| `POST` | `/auth/admin` | session | Authenticate as admin (checks password) |
| `GET` | `/stats` | none | Global stats with per-user breakdown |
| `GET` | `/stats/me` | session | Current user's stats |
| `GET` | `/admin/tone` | none | Get current tone |
| `POST` | `/admin/tone` | admin | Update tone |
| `GET` | `/admin/tone/presets` | none | List tone presets |
| `GET` | `/admin/model` | none | Get current model config |
| `POST` | `/admin/model` | admin | Update model config |
| `GET` | `/admin/model/presets` | none | List provider presets |
| `GET` | `/admin/openrouter/models` | none | Search OpenRouter models |
| `GET` | `/admin/openrouter/favorites` | none | Get curated favorites |
| `POST` | `/admin/users` | admin | List all users |
| `POST` | `/admin/users/{id}/role` | admin | Set user role |
| `POST` | `/admin/users/{id}/kick` | admin | Kick user |
| `GET` | `/admin/context` | admin | Get context stats and limits |
| `POST` | `/admin/context/reset` | admin | Clear all messages |
| `POST` | `/admin/context/settings` | admin | Update limits |

## How to run

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export LLM_API_KEY="your-key"        # or set via admin UI
export ADMIN_PASSWORD="your-pass"    # optional, defaults to "h4x0r"
python main.py                       # runs on :8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                          # runs on :5173, proxies /api -> :8000
```

### Quick test config

In the admin panel (password: value of ADMIN_PASSWORD, default `h4x0r`):
- Provider: `openrouter`
- Click "Browse OpenRouter models..." and pick from favorites
- API Key: your OpenRouter key
- Apply

### Real diffusion testing

- Provider: `inception`
- Model: `mercury-2`
- API Key: get from platform.inceptionlabs.ai (10M free tokens)
- Check "Real diffusion streaming"
- Apply

## Production deployment (chat.ussyco.de)

The app is deployed on `mail.basilisk.online` (the same server this repo lives on).

### Components

- **Nginx**: reverse proxy at `/etc/nginx/sites-enabled/chat.ussyco.de`
  - Serves frontend static files from `/home/mojo/projects/tonechat/frontend/dist`
  - Proxies `/api/*` to `127.0.0.1:8100` (strips `/api` prefix)
  - Proxies `/ws/*` to `127.0.0.1:8100` (WebSocket upgrade)
  - SSL via Let's Encrypt wildcard cert for `ussyco.de`
  - SPA fallback (`try_files ... /index.html`)
- **Systemd service**: `/etc/systemd/system/tonechat.service`
  - Runs `uvicorn main:app --host 127.0.0.1 --port 8100`
  - Uses venv at `/home/mojo/projects/tonechat/backend/venv`
  - Auto-restarts on crash

### Current state: STOPPED

The service was stopped and disabled as of session 3. To bring it back up:

```bash
sudo systemctl enable --now tonechat
```

To stop it again:

```bash
sudo systemctl stop tonechat
sudo systemctl disable tonechat
```

### Deploying new code

After making changes:

```bash
# Rebuild frontend
cd frontend && npm run build

# Restart backend (picks up Python changes)
sudo systemctl restart tonechat
```

No Docker involved. The backend runs directly from the venv, and nginx serves the built frontend files.

### After restart

The API key and all in-memory state (messages, users, sessions) are lost on restart. You need to reconfigure via the admin panel:
1. Go to https://chat.ussyco.de/, join with a name
2. Click Admin, enter password (`h4x0r` or whatever `ADMIN_PASSWORD` is set to)
3. Set provider, API key, model
4. Apply

## The big unresolved thing: diffusion

### The vision vs. what's built

The original idea was input-side diffusion: the user's raw text IS the noisy sample, and the model denoises it toward the target tone. Like img2img in Stable Diffusion.

What's actually built is output-side diffusion visualization. Mercury 2's `diffusing: true` API mode shows the denoising of the **output generation** — it starts from random noise and refines toward the answer. The user's message goes in as prompt context, not as the noise seed.

```
CURRENT:
  prompt: "rewrite X in friendly tone"  ->  Mercury 2 starts from RANDOM NOISE  ->  denoises to answer

ENVISIONED:
  "this code is garbage"  ->  IS the noisy starting point  ->  denoises toward tone  ->  "this code could use work"
```

Nobody offers the second thing as an API yet.

### Possible paths forward

1. **Multi-pass iterative refinement**: Make N calls with escalating tone strength (10% -> 40% -> 70% -> 100%), streaming each intermediate. Mercury 2 is fast enough for 3-4 passes to feel instant.
2. **Prompt-engineered pseudo-diffusion**: One call, prompt the LLM to output multiple intermediate versions. Parse and stream each step.
3. **Wait for APIs to catch up**: If someone adds an init_text parameter for text-to-text diffusion, wire it in. The WebSocket infrastructure already exists.
4. **Build your own**: Run a discrete diffusion model locally. Heavy lift.

## Known issues / things still to clean up

1. **The diffusion visualization is output-side, not input-side** — see "big unresolved thing" above.
2. **In-memory only** — messages, users, sessions, and config vanish on restart. Add SQLite or Redis if you need persistence.
3. **Original messages sent to all clients** — the backend always includes `original` in the WebSocket broadcast. The frontend hides it by default, but any WebSocket client can see the raw text.
4. **Anthropic provider** — listed in presets but Anthropic's API isn't fully OpenAI-compatible (different message format for system prompts). Will likely need special handling in `_build_request()`.
5. **Error display** — backend errors are logged server-side but the frontend just shows `[rewrite failed]` badge. Could surface actual error messages.
6. **Refusal detection is heuristic** — the pattern list in `llm.py:43-61` covers common English refusals. Non-English refusals or creatively worded refusals will slip through.
7. **Token estimation is approximate** — `word_count * 1.3` is a rough heuristic. For accurate counts, use tiktoken or the provider's token count API.
8. **No content moderation** — there is deliberately no content filtering. The prompt explicitly tells the LLM not to censor. If you need moderation, add it as a separate layer.
9. **Session persistence** — sessions are in-memory. Server restart = everyone needs to re-join. Could persist to a JSON file or SQLite.
10. **Model-dependent behavior** — the system prompt improvements work well with less-filtered models (Llama, Mistral, Mercury) but models with strong safety training (GPT-4o, Claude) may still refuse or euphemize.

## Deps

Backend: `fastapi`, `uvicorn`, `pydantic`, `httpx`, `websockets`, `python-dotenv`
Frontend: `react`, `react-dom`, `vite`, `tailwindcss`, `typescript`

## Repo

https://github.com/mojomast/diffusionchatussy
