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
    "fontknight": "agents/font-knight",
    "copywriter": "agents/copywriter",
    "critic": "agents/design-critic",
}

SITE_RULES = """Website rules:
- A single self-contained index.html. Use Tailwind via <script src="https://cdn.tailwindcss.com"></script>.
- Google Fonts and the Lucide icon script named in the notes are allowed. No other external scripts or stylesheets.
- Images: use the photos from the researcher's notes (relative paths like images/hero-1a2b3c.jpg). Only if no researched photo fits, use https://picsum.photos/seed/<one-word-topic>/<width>/<height>.
- Load the fonts font-knight chose with a <link> tag and configure Tailwind (tailwind.config in an inline script) with the brief's palette as named colours and the fonts as fontFamily.display and fontFamily.sans.
- Every major block is a <section> (or header/nav/footer) with a descriptive id and a matching data-section attribute, e.g. <section id="menu" data-section="menu">.
- Responsive, accessible (alt text, contrast), modern and polished. Real-sounding copy, never lorem ipsum.
- Icons: Lucide (<i data-lucide="name">) using only the names font-knight listed, or a small inline SVG.
- Any JavaScript goes in an inline <script> at the end of <body>.
- No emoji or symbol characters anywhere (use icons instead), and no em or en dashes: use a plain hyphen, a comma, or "to" for ranges (e.g. "Monday to Friday, 7 AM to 8 PM")."""

DESIGN_PRINCIPLES = """Design principles (every page must meet all of them):
- Art direction: commit to the brief's style direction and its signature detail. The page must look designed for this business, never like a template.
- Layout: vary the composition from section to section (split image and text, asymmetric grid, full-bleed photo, bento grid, editorial list, stat strip). Never stack identical rows of centred cards. Content sits in a max-w-6xl or max-w-7xl container with px-6 or more.
- Hierarchy: one H1 in the hero. A real type scale: hero text-5xl to text-7xl on desktop with tight leading and tracking-tight, section headings text-3xl to text-4xl, body text-base to text-lg with leading-relaxed and lines no wider than about 70 characters (max-w-prose). Small uppercase eyebrows are allowed above headings, sparingly.
- Spacing: an 8px rhythm. Sections py-20 to py-28 on desktop, py-14 on mobile. Generous whitespace beats clutter.
- Colour: neutrals for most surfaces, the primary for structure, the accent only for calls to action and key highlights. Text contrast of at least 4.5:1. Alternate section backgrounds subtly (background and surface) to separate sections. No purple-to-blue gradients, glassmorphism, or glowing blobs unless the brief asks for them.
- Imagery: photos are large and intentional, with explicit aspect ratios (aspect-[4/3], aspect-[16/9]), object-cover and rounded corners that match the style.
- Components: a sticky header with the name, 3 to 5 anchor links and one primary button, collapsing to a menu button under md. Buttons have hover, active and focus-visible states. Cards use either a hairline border or a soft shadow, not heavy versions of both.
- Copy: concrete and specific (dish names with prices in the local currency, real-sounding hours and addresses in the right city, named team members). Never "Welcome to", "Elevate", "Unleash", "Discover the magic" or filler superlatives.
- Motion: subtle and purposeful (transition-colors, a 2px hover lift, smooth scrolling with scroll-mt on anchored sections), wrapped in motion-safe: so prefers-reduced-motion is respected.
- Accessibility: semantic landmarks, alt text, labelled form fields, visible focus rings, tap targets at least 44px, no text over photos without a dark overlay.
- Mobile first: it must read well at 375px wide with no horizontal scroll."""

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

GENERATE_SYSTEM = """You are a senior web designer who builds a complete, beautiful one-page website from a short spoken description, working from the notes of a researcher, a copywriter and a typographer (font-knight).

""" + SITE_RULES + """

""" + DESIGN_PRINCIPLES + """

""" + FULL_PROTOCOL


@lru_cache(maxsize=None)
def soul(tier: str) -> str:
    path = ROOT_DIR / TIER_DIRS[tier] / "SOUL.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def edit_system(tier: str, full_rewrite: bool) -> str:
    protocol = FULL_PROTOCOL if full_rewrite else PATCH_PROTOCOL
    return f"{soul(tier)}\n\n{SITE_RULES}\n\n{DESIGN_PRINCIPLES}\n\n{protocol}"


def critic_system() -> str:
    return (
        f"{soul('critic')}\n\n{DESIGN_PRINCIPLES}\n\n{SITE_RULES}\n\n{PATCH_PROTOCOL}\n\n"
        "Fix at most 8 issues, the ones that most hurt the design. If the page already meets the principles, "
        "output only the SUMMARY line. The SUMMARY describes the finished site to the user, not your fixes."
    )


def critic_user(html: str, notes: str) -> str:
    parts = [f"Freshly built index.html to review:\n```html\n{html}\n```"]
    if notes:
        parts.append(notes)
    return "\n\n".join(parts)


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
