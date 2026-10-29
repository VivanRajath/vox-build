"""code-editor: turns spoken instructions into site versions.

jnr/snr tiers return small SEARCH/REPLACE patches (fast); the architect tier
rewrites the whole page. A patch that fails to parse or apply escalates to
the next tier, ending in a full rewrite.
"""
import asyncio
import json
import re
import textwrap
from collections import defaultdict
from html.parser import HTMLParser

from .. import events, llm, store
from . import prompts, research
from .router import ESCALATION, route

_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

SUMMARY_RE = re.compile(r"^\s*SUMMARY:\s*(.+)$", re.MULTILINE)
BLOCK_RE = re.compile(r"<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n?>>>>>>> REPLACE", re.DOTALL)
FENCE_RE = re.compile(r"```(?:html)?\s*\n(.*?)```", re.DOTALL)

# No emoji/pictographs or em/en dashes on generated pages, whatever the model writes.
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍⃣]")
DASH_RE = re.compile(r"\s*(?:—|&mdash;|&#8212;)\s*|–|&ndash;|&#8211;")

# Patches are small; whole pages need room. Lower caps also keep requests
# inside per-minute token quotas on providers like Groq.
PATCH_MAX_TOKENS = 4096
FULL_MAX_TOKENS = 12000


class EditFailed(Exception):
    pass


# ---------------------------------------------------------------------------
# Public entry points (serialized per project)
# ---------------------------------------------------------------------------

async def generate(project_id: str, description: str) -> dict:
    async with _locks[project_id]:
        events.publish(project_id, {"type": "job_started", "kind": "generate", "instruction": description, "tier": "research"})
        notes = await _research_for_generate(project_id, description)
        events.publish(project_id, {"type": "job_stage", "tier": "architect"})
        try:
            raw = await llm.complete(prompts.GENERATE_SYSTEM, prompts.generate_user(description, notes), "architect", FULL_MAX_TOKENS)
            html = _parse_full(raw)
            summary = _parse_summary(raw) or "Built your new website."
            version = store.commit(project_id, {"index.html": html}, summary, description, "architect")
        except (llm.LLMError, EditFailed) as e:
            return _fail(project_id, description, str(e))
        return _done(project_id, version)


async def edit(project_id: str, instruction: str) -> dict:
    async with _locks[project_id]:
        tier = route(instruction)
        events.publish(project_id, {"type": "job_started", "kind": "edit", "instruction": instruction, "tier": tier})
        html = store.read_index(project_id)
        meta = store.load_meta(project_id)
        notes = ""
        if research.wants_images(instruction):
            events.publish(project_id, {"type": "job_stage", "tier": "research"})
            needs = await research.image_needs(instruction, meta.get("brief"))
            images = await research.find_images(project_id, needs)
            _publish_research(project_id, None, images)
            notes = research.notes_for_prompt(None, images)
            # Fresh photos only land in the page through a patch or rewrite, so start at snr.
            tier = "snr" if tier == "jnr" else tier
            events.publish(project_id, {"type": "job_stage", "tier": tier})
        user = prompts.edit_user(instruction, html, meta.get("selection"), notes or _brief_reminder(meta.get("brief")))

        error = ""
        while tier:
            full_rewrite = tier == "architect"
            try:
                max_tokens = FULL_MAX_TOKENS if full_rewrite else PATCH_MAX_TOKENS
                raw = await llm.complete(prompts.edit_system(tier, full_rewrite), user, tier, max_tokens)
                new_html = _parse_full(raw) if full_rewrite else _apply_patches(html, raw)
                summary = _parse_summary(raw) or "Updated your website."
                version = store.commit(project_id, {"index.html": new_html}, summary, instruction, tier)
                return _done(project_id, version)
            except EditFailed as e:
                error = str(e)
                tier = ESCALATION[tier]
                if tier:
                    events.publish(project_id, {"type": "job_escalated", "tier": tier, "reason": error})
            except llm.LLMError as e:
                return _fail(project_id, instruction, str(e))
        return _fail(project_id, instruction, error or "Could not apply that change")


async def undo(project_id: str) -> dict:
    async with _locks[project_id]:
        meta = store.undo(project_id)
        if meta is None:
            return {"ok": False, "message": "There is nothing to undo."}
        version = next(v for v in meta["versions"] if v["n"] == meta["current"])
        events.publish(project_id, {"type": "version", "current": meta["current"], "versions": meta["versions"], "undo": True})
        return {"ok": True, "message": f"Undone. You're back to: {version['summary']}", "version": meta["current"]}


async def restore(project_id: str, n: int) -> dict:
    async with _locks[project_id]:
        meta = store.restore(project_id, n)
        events.publish(project_id, {"type": "version", "current": meta["current"], "versions": meta["versions"]})
        return {"ok": True, "version": n}


def describe(project_id: str) -> str:
    outline = _Outline()
    outline.feed(store.read_index(project_id))
    meta = store.load_meta(project_id)
    lines = [f"Page title: {outline.title.strip() or 'untitled'}."]
    if outline.sections:
        lines.append("Sections from top to bottom: " + "; ".join(outline.sections) + ".")
    if meta.get("selection"):
        lines.append(f"The user has selected: {meta['selection'].get('label', 'an element')}.")
    lines.append(f"There are {meta['current']} edits so far.")
    return " ".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _research_for_generate(project_id: str, description: str) -> str:
    brief = await research.brief(description)
    images = await research.find_images(project_id, brief.get("images", []))
    if brief:
        store.set_brief(project_id, brief)
    _publish_research(project_id, brief, images)
    return research.notes_for_prompt(brief, images)


def _publish_research(project_id: str, brief: dict | None, images: list[dict]) -> None:
    parts = []
    if brief:
        sections = [s.get("id", "?") for s in brief.get("sections", []) if isinstance(s, dict)]
        fonts = brief.get("fonts", {})
        parts.append(f"planned {len(sections)} sections ({', '.join(sections)})")
        if fonts:
            parts.append(f"fonts {fonts.get('heading')} + {fonts.get('body')}")
    parts.append(f"found {len(images)} photo{'s' if len(images) != 1 else ''}")
    events.publish(project_id, {
        "type": "research_done",
        "summary": "Researcher " + ", ".join(parts),
        "palette": (brief or {}).get("palette"),
        "images": [{"path": i["path"], "alt": i["alt"]} for i in images],
    })


def _brief_reminder(brief: dict | None) -> str:
    """Keeps palette and fonts consistent when an edit adds new content."""
    if not brief:
        return ""
    keep = {k: brief[k] for k in ("palette", "fonts", "tone") if k in brief}
    return "Design brief to stay consistent with:\n" + json.dumps(keep)


def _done(project_id: str, version: dict) -> dict:
    meta = store.load_meta(project_id)
    events.publish(project_id, {"type": "job_done", "version": version, "current": meta["current"], "versions": meta["versions"]})
    return {"ok": True, "message": version["summary"], "version": version["n"], "tier": version["tier"]}


def _fail(project_id: str, instruction: str, reason: str) -> dict:
    events.publish(project_id, {"type": "job_failed", "instruction": instruction, "reason": reason})
    return {"ok": False, "message": f"Sorry, that change didn't work: {reason}"}


def _parse_summary(raw: str) -> str:
    match = SUMMARY_RE.search(raw)
    return _clean_text(match.group(1).strip()) if match else ""


def _clean_text(text: str) -> str:
    text = EMOJI_RE.sub("", text)
    # Spaced em dashes read as a pause, so they become " - "; en dashes in ranges become plain hyphens.
    return DASH_RE.sub(lambda m: " - " if m.group(0).strip() != m.group(0) else "-", text)


def _parse_full(raw: str) -> str:
    match = FENCE_RE.search(raw)
    html = match.group(1) if match else raw
    start = re.search(r"<!doctype html|<html", html, re.IGNORECASE)
    if start:
        html = html[start.start():]
    end = html.lower().rfind("</html>")
    if end != -1:
        html = html[: end + len("</html>")]
    html = _clean_text(html)
    _validate(html)
    return html.strip() + "\n"


def _apply_patches(html: str, raw: str) -> str:
    blocks = BLOCK_RE.findall(raw.replace("\r\n", "\n"))
    if not blocks:
        raise EditFailed("no patch blocks in model output")
    result = html
    for search, replace in blocks:
        result = _apply_one(result, search, replace)
    # Cleans the whole page, so dashes from earlier versions disappear on the next edit too.
    result = _clean_text(result)
    _validate(result)
    return result


def _apply_one(text: str, search: str, replace: str) -> str:
    count = text.count(search)
    if count == 1:
        return text.replace(search, replace, 1)
    if count > 1:
        raise EditFailed("patch target is ambiguous")

    # Whitespace-tolerant fallback: match stripped lines, keep the file's indentation.
    lines = text.split("\n")
    wanted = [line.strip() for line in search.split("\n")]
    hits = [
        i for i in range(len(lines) - len(wanted) + 1)
        if [line.strip() for line in lines[i : i + len(wanted)]] == wanted
    ]
    if len(hits) != 1:
        raise EditFailed("patch target not found in the page")
    i = hits[0]
    indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
    replaced = [indent + line if line.strip() else line for line in textwrap.dedent(replace).split("\n")] if replace else []
    return "\n".join(lines[:i] + replaced + lines[i + len(wanted) :])


def _validate(html: str) -> None:
    lower = html.lower()
    if "<html" not in lower or "</html>" not in lower or "<body" not in lower or len(html) < 200:
        raise EditFailed("model returned an incomplete page")


class _Outline(HTMLParser):
    """Collects the title and a label per top-level section for describe_site."""

    BLOCKS = {"section", "header", "nav", "footer", "main"}

    def __init__(self):
        super().__init__()
        self.title = ""
        self.sections: list[str] = []
        self._in_title = False
        self._pending: str | None = None
        self._heading = False
        self._depth = 0  # how many recorded blocks we are inside

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag in self.BLOCKS:
            # Only top-level blocks count; a <footer> inside a testimonial card is not a section.
            if self._depth == 0 and (attrs.get("data-section") or attrs.get("id") or tag != "main"):
                self._pending = attrs.get("data-section") or attrs.get("id") or tag
                self.sections.append(self._pending)
            if tag != "main":
                self._depth += 1
        elif tag in ("h1", "h2", "h3") and self._pending:
            self._heading = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in ("h1", "h2", "h3"):
            self._heading = False
        elif tag in self.BLOCKS and tag != "main" and self._depth:
            self._depth -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._heading and self._pending and data.strip():
            self.sections[-1] = f"{self._pending} (\"{data.strip()[:60]}\")"
            self._pending = None
            self._heading = False
