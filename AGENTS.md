# Vox Build agents

## Agent Hierarchy

```
Vox (Bolna voice agent)  ── bolna/agent_prompt.md, scripts/create_agent.py
│   Talks to the user, calls custom functions:
│   generate_site · edit_site · undo_change · describe_site · check_progress
│
└── vox-build backend (orchestrator)  ── backend/main.py
    │
    ├── researcher ────────────────── backend/editor/research.py
    │     Design brief, art direction + real photos before building
    │
    ├── font-knight ──────────────── backend/editor/fontknight.py
    │     Real Google Fonts pairing + Lucide icons, searched from live catalogues
    │
    ├── copywriter ───────────────── backend/editor/copywriter.py
    │     Headline, calls to action and section copy in the brief's tone
    │
    ├── design-critic ────────────── backend/editor/engine.py (_review)
    │     Reviews each new page against the design principles, patches the worst issues
    │
    ├── intent-router ────────────── backend/editor/router.py
    │     Classifies a spoken edit → tier
    │
    └── code-editor ──────────────── backend/editor/engine.py
        ├── jnr-developer ────────── Tier jnr: small visual tweaks (fast model, patches)
        ├── snr-developer ────────── Tier snr: sections & features (standard model, patches)
        └── architect ────────────── Tier architect: redesigns & fallback (top model, full rewrite)
```

The personas in `agents/*/SOUL.md` and `agents/code-editor/agents/*/SOUL.md`
are loaded as live system prompts, so editing them changes runtime behaviour.
Every builder also gets the shared `DESIGN_PRINCIPLES` in `backend/editor/prompts.py`.

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
| check_progress | project_id | `{status, message}` for the latest background job |

`status` is `done`, `in_progress` (finishes in the background, preview updates via SSE) or `failed`.

## researcher

**Persona:** `agents/researcher/SOUL.md` · **Model:** the jnr model (own rate-limit quota on Groq)
**Input:** spoken site description, or an edit that mentions photos
**Output:** a design brief (stored in the project for later edits) plus photos saved to `site/images/`

- Brief: business, industry, audience, tone, art direction (style, layout, type mood, signature detail), palette, 5-8 sections with concrete elements, image slots with search queries
- JSON mode, and one retry when the brief comes back empty or half-shaped
- Photos: Pexels when `PEXELS_API_KEY` is set, otherwise Wikimedia Commons; a simpler fallback query is tried when the specific one finds nothing; credits go in the footer
- Edits that mention photos get a fresh image search and start at the snr tier

## font-knight

**Persona:** `agents/font-knight/SOUL.md` · **Model:** the jnr model
**Input:** the brief · **Output:** heading + body families, a Google Fonts URL, Lucide icon names (stored in the brief as `typography`)

- Downloads the Google Fonts catalogue once (cached in `data/cache/`) and shows the model a shortlist of popular families per category, minus overused defaults (Inter, Roboto, Poppins...)
- Any family the model invents is rejected; display and script faces can't be the body font
- Icons: the model names concepts, font-knight searches Lucide's tag list (synonyms, then names, then tags), so only real icons are used

## copywriter

**Persona:** `agents/copywriter/SOUL.md` · **Model:** the jnr model · runs in parallel with font-knight and the photo search
**Output:** headline, subheadline, CTAs, per-section eyebrow/heading/body/items, footer line

## design-critic

**Persona:** `agents/design-critic/SOUL.md` · **Model:** the snr model
**Input:** the architect's new page + brief · **Output:** up to 8 SEARCH/REPLACE fixes, applied one by one (a stale fix is skipped, a broken result keeps the architect's page). Set `DESIGN_CRITIC=0` to skip it.

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
    ├── new website ───────> generate_site ──> researcher ──> font-knight + copywriter + photos ──> architect ──> design-critic
    ├── change ────────────> edit_site ──> [researcher if photos] ──> intent-router ──> jnr | snr | architect
    │                                                       (escalates on failure)
    ├── undo ──────────────> undo_change ──> store.undo
    └── "what's on it?" ───> describe_site ──> HTML outline (no LLM)
```
