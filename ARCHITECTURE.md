# Architecture

## 1. Overview

Vox Build turns speech into website versions. Three systems cooperate:

| Component | Responsibility |
|---|---|
| **Bolna voice agent (Vox)** | Listens (Deepgram), decides what the user wants (LLM), talks back (Cartesia), and calls our custom functions |
| **FastAPI backend** | Mints web-call sessions, runs the edit pipeline, stores versions, serves previews, pushes events |
| **React frontend** | Mic + call state, live preview iframe, element picker, activity log, version timeline |

The core design choice, carried over from the original tiered agent system, is **cost- and latency-aware delegation**. Most voice edits are small ("make it blue"), so they go to a fast, cheap model that returns tiny patches. Only real redesigns pay for a top-tier model that rewrites the whole page.

## 2. Request flow (one voice edit)

```
User speaks: "make the header dark green"
  │
  ▼
Bolna: STT → agent LLM decides → custom function edit_site
  │  POST {PUBLIC_BASE_URL}/tools/edit_site
  │  Authorization: Bearer TOOL_SECRET
  │  {"project_id": "<from user_data>", "instruction": "Make the header dark green"}
  │  (meanwhile Vox speaks the pre_call_message: "On it.")
  ▼
backend.main.tool_edit_site
  │  resolves project (project_id, or the project of the last minted session)
  │  starts engine.edit() as a task, waits up to TOOL_SYNC_WAIT seconds
  ▼
engine.edit  (serialized per project by an asyncio.Lock)
  │  router.route() → "jnr"
  │  llm.complete(jnr SOUL + site rules + patch protocol, page + selection + instruction)
  │  parse SEARCH/REPLACE blocks → apply (exact, then whitespace-tolerant)
  │  on failure: escalate jnr → snr → architect (full rewrite)
  │  validate HTML → store.commit() → events.publish("job_done")
  ▼
Tool response {"status": "done", "message": "Made the header dark green."}
  │                     or {"status": "in_progress", ...} if still running
  ▼
Vox: "Done, the header is dark green now. What next?"

In parallel: browser EventSource gets job_done → iframe reloads (scroll kept)
```

## 3. Components

### 3.1 Bolna integration

- **Web Call SDK** (`@bolna/web-call`): the browser calls `start()` from a click, and the SDK POSTs `{user_data}` to `/api/bolna-session`. The backend forwards it to `POST https://api.bolna.ai/web-call/session` with the API key and returns the single-use session (about 120s TTL).
- **user_data → prompt variable**: `{project_id}` in `bolna/agent_prompt.md` is filled per call. Each custom function declares a `project_id` parameter, and Bolna substitutes prompt variables into function parameters.
- **Fallback**: if a tool call arrives with an unsubstituted id, the backend uses the project of the most recently minted session.
- **Custom functions** (defined in `scripts/create_agent.py`):

| Function | Endpoint | Purpose |
|---|---|---|
| `generate_site` | `/tools/generate_site` | Build a new site from a description |
| `edit_site` | `/tools/edit_site` | Any change (generates instead if the project is still blank) |
| `undo_change` | `/tools/undo_change` | Revert to the previous version |
| `describe_site` | `/tools/describe_site` | Outline of the current page (no LLM call) |

- The Web Call SDK has no transcript events, so the UI's activity log is driven by our own SSE events from the edit pipeline.

### 3.2 researcher (`backend/editor/research.py`)

Runs before the developers so sites aren't built on guesses:

1. **Design brief** (one fast LLM call, JSON): business, audience, tone, palette, Google Fonts pairing, 5-8 sections with concrete elements, and image slots with a specific query plus a 1-2 word fallback query. Stored in `meta.json` and fed back into later edits so new content keeps the same palette and fonts.
2. **Photos**: for each slot, search Pexels (if `PEXELS_API_KEY`) or Wikimedia Commons, skip logos/maps/diagrams and tiny images, prefer landscape, then download a 1280px version into `site/images/`. Local files mean no hotlink failures, and undo snapshots include them. Credits are added to the footer.
3. Results stream to the UI as a `research_done` event (palette swatches + photo thumbnails in the activity log).

### 3.3 intent-router (`backend/editor/router.py`)

A keyword classifier. An LLM classifier would add a round trip of dead air on every voice edit, and misroutes are cheap because of escalation.

| Tier | Triggers | Output protocol |
|---|---|---|
| `architect` | redesign, start over, dark mode, new theme, rebuild… | Full `index.html` |
| `snr` | add a…, section, gallery, form, remove, move, long instructions | SEARCH/REPLACE patches |
| `jnr` | everything else (colours, sizes, text, single elements) | SEARCH/REPLACE patches |

### 3.4 code-editor (`backend/editor/engine.py`)

- **Prompts**: each tier's persona is its GitAgent `SOUL.md` (`agents/code-editor/agents/*/SOUL.md`). Site rules and output protocols are appended in `prompts.py`, because the parser depends on them.
- **Selection context**: when the user has picked an element, its CSS path and `outerHTML` go into the prompt, so "this" and "it" resolve.
- **Patch application**: exact unique match first. Otherwise a line-wise stripped-whitespace match that keeps the file's indentation. If neither matches, `EditFailed` triggers escalation.
- **Validation**: the result must be a full HTML document, or it's rejected (and escalated).
- **describe**: an `HTMLParser` pass that lists the title and sections (`data-section` / `id` plus the first heading).

### 3.5 Store (`backend/store.py`)

```
data/projects/<id>/
  meta.json      versions[], current, selection
  site/          what the preview serves
  history/<n>/   snapshot per version
```

History is linear, like an editor's undo stack. Undo moves `current` back, and a new edit after an undo discards the undone versions.

### 3.6 Preview

`/preview/<id>/` serves the site and injects `preview_inject.js` before `</body>`. The script:
- keeps the scroll position across reloads (`sessionStorage`)
- implements pick mode (hover outline, click → `postMessage` with CSS path, HTML and label)
- highlights the current selection

### 3.7 LLM layer (`backend/llm.py`)

Anthropic goes through the official `anthropic` SDK, with effort `low` for patches and `medium` for full rewrites. Sonnet 5.5 and Opus 5.5 requests opt into server-side refusal fallback. OpenAI and Gemini go through the `openai` SDK (Gemini via its OpenAI-compatible endpoint). Refusals, truncation and API errors become `LLMError`, which reaches the user as a short spoken apology.

## 4. Latency budget

| Step | Typical |
|---|---|
| Bolna STT + agent LLM decision | ~1s |
| `pre_call_message` spoken | covers the wait |
| jnr patch (small model, low effort, small output) | 2-5s |
| snr patch | 4-10s |
| architect rewrite / first generation | 20-60s, returns "working on it" and finishes in the background |
| SSE → iframe reload | <300ms |

## 5. Agent specs (GitAgent)

The `agents/` tree keeps the GitAgent layout (`agent.yaml`, `SOUL.md`, `SKILL.md`, `DUTIES.md`). The code-editor tier specs are live: their `SOUL.md` files are loaded as system prompts. The `repo-scanner` specs come from the original repo-sandbox-agent and are not used by the voice runtime.
