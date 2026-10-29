# Vox Build agents

## Agent Hierarchy

```
Vox (Bolna voice agent)  ── bolna/agent_prompt.md, scripts/create_agent.py
│   Talks to the user, calls custom functions:
│   generate_site · edit_site · undo_change · describe_site
│
└── vox-build backend (orchestrator)  ── backend/main.py
    │
    ├── researcher ────────────────── backend/editor/research.py
    │     Design brief + real photos before building
    │
    ├── intent-router ────────────── backend/editor/router.py
    │     Classifies a spoken edit → tier
    │
    └── code-editor ──────────────── backend/editor/engine.py
        ├── jnr-developer ────────── Tier jnr: small visual tweaks (fast model, patches)
        ├── snr-developer ────────── Tier snr: sections & features (standard model, patches)
        └── architect ────────────── Tier architect: redesigns & fallback (top model, full rewrite)
```

The tier personas in `agents/code-editor/agents/*/SOUL.md` are loaded as live
system prompts, so editing them changes runtime behaviour.

---

## Vox (Bolna voice agent)

**Prompt:** `bolna/agent_prompt.md` (`{project_id}` comes from web-call `user_data`)
**Pipeline:** Deepgram nova-3 → Bolna-hosted LLM → Cartesia sonic-3.5
**Functions:** POST `{PUBLIC_BASE_URL}/tools/<name>` with `Authorization: Bearer TOOL_SECRET`

| Function | Params | Returns |
|---|---|---|
| generate_site | project_id, description | `{status, message}` |
| edit_site | project_id, instruction | `{status, message}` |
| undo_change | project_id | `{status, message}` |
| describe_site | project_id | `{status, message}` |

`status` is `done`, `in_progress` (finishes in the background, preview updates via SSE) or `failed`.

## researcher

**Persona:** `agents/researcher/SOUL.md` · **Model:** the jnr model (own rate-limit quota on Groq)
**Input:** spoken site description, or an edit that mentions photos
**Output:** a design brief (stored in the project for later edits) plus photos saved to `site/images/`

- Brief: business, industry, audience, tone, palette, Google Fonts, 5-8 sections with concrete elements, image slots with search queries
- Photos: Pexels when `PEXELS_API_KEY` is set, otherwise Wikimedia Commons; a simpler fallback query is tried when the specific one finds nothing; credits go in the footer
- Edits that mention photos get a fresh image search and start at the snr tier

## intent-router

**Input:** spoken instruction (English, written by Vox)
**Output:** `jnr` | `snr` | `architect`

- **Low** (colour, size, wording, one element) → `jnr`
- **Medium** (add/remove/move sections, forms, galleries, interactions) → `snr`
- **High** (redesign, theme change, start over) → `architect`

## code-editor

**Input:** instruction + current index.html + optional selected element + tier
**Output:** a new committed version with a one-sentence spoken summary

| Sub-agent | Default model (Anthropic) | Output | On failure |
|---|---|---|---|
| jnr-developer | claude-haiku-5-5 | SEARCH/REPLACE patches | escalate to snr |
| snr-developer | claude-sonnet-5-5 | SEARCH/REPLACE patches | escalate to architect |
| architect | claude-opus-5-5 | full index.html | report failure |

OpenAI and Gemini equivalents are in `backend/config.py`.

## Legacy: repo-scanner

`agents/repo-scanner/` (framework-detector, deep-scan-agent) comes from the
original repo-sandbox-agent. It is not used by the voice runtime.

## Delegation Flow

```
Spoken request
    │
    ├── new website ───────> generate_site ──> researcher ──> architect (full page)
    ├── change ────────────> edit_site ──> [researcher if photos] ──> intent-router ──> jnr | snr | architect
    │                                                       (escalates on failure)
    ├── undo ──────────────> undo_change ──> store.undo
    └── "what's on it?" ───> describe_site ──> HTML outline (no LLM)
```
