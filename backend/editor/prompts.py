"""System prompts. Each tier's persona lives in its GitAgent SOUL.md so the
agent specs stay the source of truth; output protocols are defined here
because the parser in engine.py depends on them."""
from functools import lru_cache

from ..config import ROOT_DIR

TIER_DIRS = {
    "jnr": "agents/code-editor/agents/jnr-developer",
    "snr": "agents/code-editor/agents/snr-developer",
    "architect": "agents/code-editor/agents/architect",
    "research": "agents/researcher",
}

SITE_RULES = """Website rules:
- A single self-contained index.html. Use Tailwind via <script src="https://cdn.tailwindcss.com"></script>.
- Google Fonts are allowed. No other external scripts or stylesheets.
- Images: use the photos from the researcher's notes (relative paths like images/hero-1a2b3c.jpg). Only if no researched photo fits, use https://picsum.photos/seed/<one-word-topic>/<width>/<height>.
- Load the brief's Google Fonts with a <link> tag and configure Tailwind (tailwind.config in an inline script) with the brief's palette and fonts.
- Every major block is a <section> (or header/nav/footer) with a descriptive id and a matching data-section attribute, e.g. <section id="menu" data-section="menu">.
- Responsive, accessible (alt text, contrast), modern and polished. Real-sounding copy, never lorem ipsum.
- Any JavaScript goes in an inline <script> at the end of <body>.
- No emoji or symbol characters anywhere (use small inline SVG icons instead), and no em or en dashes: use a plain hyphen, a comma, or "to" for ranges (e.g. "Monday to Friday, 7 AM to 8 PM")."""

PATCH_PROTOCOL = """Output format (strict, nothing else):
SUMMARY: <one short past-tense sentence describing the change, friendly enough to be spoken aloud>
<<<<<<< SEARCH
<exact lines copied from the current file>
=======
<replacement lines>
>>>>>>> REPLACE

You may emit several SEARCH/REPLACE blocks. Each SEARCH must match the current file exactly (same whitespace) and be unique in it; include a few surrounding lines if needed. Keep blocks small. Never output the whole file."""

FULL_PROTOCOL = """Output format (strict, nothing else):
SUMMARY: <one short past-tense sentence describing the change, friendly enough to be spoken aloud>
```html
<the complete new index.html>
```"""

GENERATE_SYSTEM = """You are a senior web designer who builds a complete, beautiful one-page website from a short spoken description.

""" + SITE_RULES + """

""" + FULL_PROTOCOL


@lru_cache(maxsize=None)
def soul(tier: str) -> str:
    path = ROOT_DIR / TIER_DIRS[tier] / "SOUL.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def edit_system(tier: str, full_rewrite: bool) -> str:
    protocol = FULL_PROTOCOL if full_rewrite else PATCH_PROTOCOL
    return f"{soul(tier)}\n\n{SITE_RULES}\n\n{protocol}"


def generate_user(description: str, research_notes: str) -> str:
    parts = [f"Build this website: {description}"]
    if research_notes:
        parts.append(research_notes)
    return "\n\n".join(parts)


def edit_user(instruction: str, html: str, selection: dict | None, research_notes: str = "") -> str:
    parts = [f"Current index.html:\n```html\n{html}\n```"]
    if research_notes:
        parts.append(research_notes)
    if selection:
        snippet = (selection.get("html") or "")[:2000]
        parts.append(
            "The user has clicked this element in the preview, so words like \"this\", \"it\" or \"here\" refer to it "
            f"(CSS path: {selection.get('path', '?')}):\n```html\n{snippet}\n```"
        )
    parts.append(f"Spoken instruction from the user: {instruction}")
    return "\n\n".join(parts)
