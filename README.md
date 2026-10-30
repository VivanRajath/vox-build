# Vox Build

**Build and edit a website by talking to it.**

[![Pitch deck](https://img.shields.io/badge/Pitch_deck-Open-C2331F?style=for-the-badge)](https://vivanrajath.github.io/buildathon-deck/)
[![Demo video](https://img.shields.io/badge/Demo_video-Watch_on_Loom-15171C?style=for-the-badge)](https://www.loom.com/share/fc5195a409e84af18a43ca9baddb31f4)
[![Bolna Buildathon](https://img.shields.io/badge/Bolna-Buildathon_2026-4A505A?style=for-the-badge)](https://www.bolna.ai/symphony/buildathon)

Describe a website out loud and it appears. Then keep talking: *"make the header dark green"*, *"add a testimonials section"*, *"undo that"*. Click any element and say *"make **this** bigger"*. Every change lands in the live preview while the voice agent, Vox, talks back.

Vox is a [Bolna](https://www.bolna.ai) voice agent. Behind it, a team of AI agents researches, writes, designs and builds the site while you watch.

## Pitch deck and demo

| | |
|---|---|
| **Pitch deck** | [vivanrajath.github.io/buildathon-deck](https://vivanrajath.github.io/buildathon-deck/): 13 slides on the problem, the product, the agent team and how it is built on Bolna. Use the arrow keys, click or swipe; `F` for full screen. |
| **Demo video** | [Watch on Loom](https://www.loom.com/share/fc5195a409e84af18a43ca9baddb31f4). It is also embedded on slide 4 of the deck. |

## The agent team

Vox is the only agent you talk to. Every other agent has one job, and its persona lives in `agents/*/SOUL.md`, loaded as a live system prompt.

| Agent | Job |
|---|---|
| **Vox** | The Bolna voice agent. Listens, talks back and calls the build functions. |
| **Researcher** | Writes the design brief (audience, tone, art direction, palette, sections) and finds real photos for every image slot. |
| **Font Knight** | Picks a real Google Fonts pairing and Lucide icons, searched from the live catalogues. |
| **Copywriter** | Writes headlines, calls to action and section copy in the brief's tone. |
| **Architect** | Builds the full page from the plan, and handles redesigns. |
| **Design Critic** | Reviews every new page against the design principles and patches the worst issues. |
| **Intent Router** | Sorts each spoken edit into small, bigger or full. |
| **Junior Dev** | A fast, cheap model for small tweaks, applied as precise patches. |
| **Senior Dev** | A stronger model for new sections and layout changes. |

A new site goes **Researcher, then Font Knight + Copywriter + photo search in parallel, then Architect, then Design Critic**. An edit goes through the Intent Router to the cheapest developer that can do it, and moves up a level automatically if its patch can't be applied. See [AGENTS.md](AGENTS.md) for the full hierarchy.

## How it works

```
Browser (React)                          FastAPI backend                       Bolna
──────────────────                       ──────────────────────                ─────────────────────
Mic button ── @bolna/web-call ─────────────────────────────────────────────▶  Vox voice agent
   │   session from /api/bolna-session ─▶ mints single-use session            Deepgram STT → LLM
   │   (user_data: { project_id })        (API key stays server-side)         → Cartesia TTS
   │                                                                              │
   │                                      /tools/edit_site  ◀── custom function ──┘
   │                                         │                  (POST, mid-conversation)
   │                                         ▼
   │                                      agent team (router → jnr / snr / architect)
   │                                         │   (cheap model → strong model)
   │                                         ▼
   │                                      new version of the site
   ▼                                         │
Live preview iframe ◀── SSE "job_done" ──────┘
```

1. The browser starts a **Bolna Web Call** and passes the current `project_id` as `user_data`. Bolna substitutes it into the agent prompt.
2. When you ask for something, Vox calls a **custom function** on this backend: `generate_site`, `edit_site`, `undo_change`, `describe_site` or `check_progress`.
3. For a new site, the planning agents (Researcher, Font Knight, Copywriter) prepare the brief, type, copy and photos; the Architect builds the page and the Design Critic reviews it.
4. For an edit, the **Intent Router** picks a developer. Small tweaks go to a fast model that returns tiny SEARCH/REPLACE patches, features to a standard model, redesigns to the top model.
5. The new version is saved (with undo history) and pushed to the browser over **Server-Sent Events**. The preview reloads and keeps your scroll position.
6. Quick edits come back within `TOOL_SYNC_WAIT` seconds, so Vox can confirm the exact change. Longer builds return "working on it" right away, finish in the background, and Vox reports back with `check_progress`, so the call never goes silent.

## Features

- **Voice-first** site generation and editing (Bolna Web Call SDK + custom functions)
- **Point and speak**: click an element in the preview, then say "make this rounder"
- **Undo by voice**, plus a clickable version timeline
- **Ask about the page**: "what's on my page?" gets a spoken outline
- **Multilingual**: Vox replies in your language and writes edit instructions in English
- **Real design inputs**: researched briefs, real Google Fonts, real icons, real photos
- **Cost- and latency-aware** model tiers with automatic escalation
- **Settings, no sign-in needed**: add any number of API keys (Anthropic, OpenAI, Gemini, Groq or any OpenAI-compatible endpoint, several per provider), each tested before it is saved. Pick a provider and model per tier and add a Pexels key for photos. When a key is rate limited, the next key for that provider takes over
- **Accounts**: sign in with Google or GitHub
- **Ship it**: download the site as a ZIP, or push it to a new or existing GitHub repo in one commit
- Desktop / tablet / mobile preview sizes, and a typed fallback for every voice action

## Quick start

Requirements: Python 3.11+, Node 18+, a Bolna account, and one LLM key (Anthropic, OpenAI, Gemini or Groq).

```bash
# 1. Backend
python -m venv .venv
.venv/Scripts/activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env              # fill in your keys

# 2. Frontend
cd frontend && npm install && npm run build && cd ..

# 3. Run (serves the built frontend too)
uvicorn backend.main:app --port 8000
```

Open http://localhost:8000. Typed commands work as soon as an LLM key is set.

### Turning on voice (deploy)

During a call, Bolna's cloud calls the backend's `/tools/*` endpoints, so voice needs the backend deployed at a public HTTPS URL. The repo ships a `Dockerfile` (frontend and backend in one container) and a Render blueprint:

1. Push the repo to GitHub.
2. In [Render](https://render.com): **New + → Blueprint**, then pick the repo. It reads `render.yaml`.
3. Fill in `BOLNA_API_KEY` and one LLM key when prompted. `TOOL_SECRET` is generated for you.
4. Once it's live, copy the service URL (e.g. `https://vox-build.onrender.com`) and `TOOL_SECRET` from Render into your local `.env` as `PUBLIC_BASE_URL` and `TOOL_SECRET`, then create the agent:

```bash
python scripts/create_agent.py            # prints BOLNA_AGENT_ID
python scripts/create_agent.py --update   # push prompt/function changes later
python scripts/create_agent.py --dump     # function JSON to paste in the dashboard instead
```

5. Add `BOLNA_AGENT_ID` to the Render environment. The service redeploys and the mic button goes live.

The same image runs on Railway, Fly.io or any Docker host: set the env vars from `.env.example` and point `PUBLIC_BASE_URL` at it. Render's free plan sleeps when idle and has no persistent disk, so open the app once before a demo, and expect projects to reset on redeploy.

If the mic errors with "Web calls aren't enabled", ask Bolna to enable web calls on your account.

### Development mode

```bash
uvicorn backend.main:app --port 8000 --reload
cd frontend && npm run dev        # http://localhost:5173, proxies to :8000
```

## Configuration

| Variable | Purpose |
|---|---|
| `BOLNA_API_KEY` | Bolna API key. Used server-side only, to mint web-call sessions and create the agent |
| `BOLNA_AGENT_ID` | The Vox agent created by `scripts/create_agent.py` |
| `PUBLIC_BASE_URL` | Public https URL of this backend, used in the custom-function URLs |
| `TOOL_SECRET` | Shared secret Bolna sends as `Authorization: Bearer …` on tool calls |
| `TOOL_SYNC_WAIT` | Seconds a tool call waits before answering "working on it" (default 8) |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY` | Server-wide LLM keys, used after a user's own keys from Settings. Each may hold several comma-separated keys, rotated on rate limits. The first provider set is the default, or force one with `LLM_PROVIDER` |
| `PEXELS_API_KEY` | Optional. Better stock photos for the researcher; without it photos come from Wikimedia Commons |
| `MODEL_JNR` / `MODEL_SNR` / `MODEL_ARCHITECT` / `MODEL_RESEARCH` | Optional per-tier model overrides (research defaults to the jnr model) |
| `SESSION_SECRET` | Signs the login cookie and encrypts stored GitHub tokens and user API keys. Auto-generated into `data/.session_secret` if unset; set it explicitly in production |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Optional. Google sign-in. Redirect URI: `<site>/auth/google/callback` |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | Optional. GitHub sign-in and push (scope `repo`). Callback URL: `<site>/auth/github/callback` |
| `BOLNA_LLM_PROVIDER`, `BOLNA_LLM_MODEL`, `BOLNA_VOICE`, `BOLNA_VOICE_ID`, `BOLNA_STT_LANGUAGE` | Optional overrides for the voice agent created by the script |

Default tier models:

| Tier | Anthropic | OpenAI | Gemini | Groq |
|---|---|---|---|---|
| jnr (small tweaks) | `claude-haiku-5-5` | `gpt-4.1-mini` | `gemini-2.5-flash` | `qwen/qwen3.8-27b` |
| snr (features) | `claude-sonnet-5-5` | `gpt-4.1` | `gemini-2.5-pro` | `openai/gpt-oss-120b` |
| architect (redesigns) | `claude-opus-5-5` | `gpt-4.1` | `gemini-2.5-pro` | `openai/gpt-oss-120b` |

### Settings and accounts

The **Settings** button in the top bar works without signing in: keys are saved to a guest account tied to the browser (encrypted on the server). Signing in later turns that guest into a full account and keeps its keys and projects.

To enable Google / GitHub sign-in (needed for Push to GitHub):

1. **Google**: Google Cloud Console > APIs & Services > Credentials > Create OAuth client ID (Web application). Add `http://localhost:8000/auth/google/callback` (and/or `http://localhost:5173/...` for Vite dev, and your deployed URL) as an authorized redirect URI.
2. **GitHub**: github.com/settings/developers > New OAuth App. Callback URL `http://localhost:8000/auth/github/callback` (a GitHub OAuth App takes one callback URL, so create one app per environment).
3. Put the four values in `.env` and restart.

A project is owned by the account (or guest) that first works on it. Its edits, typed or by voice, use the owner's keys from Settings first, then the server's `.env` keys. Pushing replaces the repo's default branch contents with the current version as one new commit (earlier history is kept).

## Repository layout

```
backend/
  main.py            FastAPI app: browser API, Bolna session mint, /tools/*, preview, zip, push
  auth.py            Google / GitHub OAuth sign-in
  users.py           accounts, encrypted GitHub tokens and per-user AI settings
  github.py          push a site to a repo as one commit (Git Data API)
  editor/research.py researcher: design brief + photo search (Pexels / Wikimedia)
  editor/router.py   intent-router: instruction → tier
  editor/engine.py   code-editor: generate, patch, escalate, undo, describe
  editor/prompts.py  system prompts (tier personas load from agents/*/SOUL.md)
  llm.py             Anthropic / OpenAI / Gemini / Groq completion, per-user keys
  store.py           projects on disk with version history
  events.py          SSE fan-out
  preview_inject.js  element picker + scroll keeper injected into previews
bolna/agent_prompt.md   Vox's system prompt
scripts/create_agent.py Creates/updates the Bolna agent and its custom functions
frontend/               Vite + React app (preview, voice panel, activity, versions)
agents/                 GitAgent specs. code-editor tier SOUL.md files are live prompts
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design details and [AGENTS.md](AGENTS.md) for the agent hierarchy.

## Security notes

- The Bolna API key never reaches the browser. The SDK only receives short-lived, single-use sessions.
- `/tools/*` requires `TOOL_SECRET` when it is set. Always set it on a public deployment.
- Generated sites are served from `/preview/<id>/` with path-traversal checks and a `Content-Security-Policy: sandbox` header (no `allow-same-origin`). Anyone with a project link can edit a page, so its scripts run in an opaque origin and can't use the viewer's login to call the API.
- User API keys and GitHub tokens are encrypted at rest and never sent back to the browser. Custom model base URLs must be public `https://` addresses.

---

Built by Vivan Rajath for the [Bolna Buildathon 2026](https://www.bolna.ai/symphony/buildathon). [Pitch deck](https://vivanrajath.github.io/buildathon-deck/) · [Demo video](https://www.loom.com/share/fc5195a409e84af18a43ca9baddb31f4)
