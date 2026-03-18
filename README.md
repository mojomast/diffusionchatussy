# Tchaikovskussy

Tchaikovskussy is a communication-first multilingual chat app. Each person chooses the language they want to write in and the language they want to read in, and the system acts like a BabelFish middle layer so people across languages can talk naturally.

This branch is the transition branch from the older tone-heavy product into a cleaner communication tool. Some legacy style-layer controls still exist in the admin/backend, but the product direction here is language mediation first.

## Core Idea

```text
User types in their speaking language
        |
        v
Backend stores the sender's chosen language context
        |
        v
Each recipient gets the message translated into their preferred hearing language
        |
        v
People using different languages can converse in one room
```

## Product Direction

- communication-first multilingual chat
- separate user preferences for `speaking_language` and `perceiving_language`
- admin-managed allowed languages
- unilateral translation for each recipient
- legacy tone/style features kept only temporarily while this is forked into a new repo

Planned repo destination for the new product:
- `mojomast/Tchaikovskussy`

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- An API key for model-backed translation

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export LLM_API_KEY="your-key-here"
export ADMIN_PASSWORD="your-password"
python main.py
```

Backend runs at `http://localhost:8000`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` and proxies API calls to the backend.

### 3. Use It

1. Open `http://localhost:5173`
2. Join with a username
3. Open **Settings**
4. Choose:
   - `I speak`
   - `I hear`
5. Enable BabelFish translation
6. Start chatting in your own language

### 4. Admin Setup

1. Open **Admin**
2. Enter the admin password
3. Configure:
   - model/provider
   - allowed languages
   - any temporary legacy style-layer settings still needed during migration

## BabelFish Preferences

Each user has these key settings:

- `speaking_language` — the language they intend to write in
- `perceiving_language` — the language they want to read in
- `translation_enabled` — whether incoming chat should be mediated into their hearing language

This creates a unilateral translation model:
- one sender writes once
- each recipient receives a version translated for them

## Current Branch Notes

This branch still contains some legacy implementation pieces from the older product:

- room tone config
- optional style/tone transformation pipeline
- diffusion-related model settings

Those are not the long-term point of Tchaikovskussy. The fork should progressively strip those out and keep only the multilingual communication stack.

## API Highlights

### Auth

```text
POST /auth/join
GET  /auth/session
POST /auth/admin
```

### User Preferences

```text
GET  /preferences
POST /preferences
```

Example update payload:

```json
{
  "translation_enabled": true,
  "speaking_language": "English",
  "perceiving_language": "Spanish"
}
```

### Admin Personalization

```text
GET  /admin/personalization
POST /admin/personalization
```

Example admin payload:

```json
{
  "available_languages": ["English", "Spanish", "German", "Japanese"],
  "allow_user_tone_prompt_edit": false,
  "tone_prompt_presets": [
    { "id": "none", "label": "None", "prompt": "" }
  ]
}
```

## Development Status

Implemented on this branch:
- BabelFish-style speak/hear language settings
- admin-controlled language availability
- personalized recipient-side translation flow
- updated UI copy toward communication-first chat

Still to do for the full fork:
- remove remaining tone/style code paths entirely
- rename repo/package/service identifiers away from ToneChat
- simplify admin UI around language mediation only
- migrate this branch into `mojomast/Tchaikovskussy`
