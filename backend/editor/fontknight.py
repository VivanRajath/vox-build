"""font-knight: picks real Google Fonts and Lucide icons for a site.

Searches the live Google Fonts catalogue and Lucide's icon tags, so every
family and icon name handed to the developers actually exists. The model
only chooses from a shortlist; anything it invents is replaced.
"""
import asyncio
import json
import logging
import re
from urllib.parse import quote_plus

import httpx

from .. import config, llm
from . import prompts
from .research import parse_json

log = logging.getLogger("vox-build.fontknight")

CATALOG_URL = "https://fonts.google.com/metadata/fonts"
LUCIDE_VERSION = "1.52.0"
LUCIDE_TAGS_URL = f"https://unpkg.com/lucide-static@{LUCIDE_VERSION}/tags.json"
LUCIDE_SCRIPT = f"https://unpkg.com/lucide@{LUCIDE_VERSION}/dist/umd/lucide.min.js"
CACHE_DIR = config.DATA_DIR.parent / "cache"

# The faces every generated site defaults to. Kept off the shortlist so pages stop looking alike.
OVERUSED = {
    "Inter", "Roboto", "Open Sans", "Poppins", "Montserrat", "Lato", "Raleway", "Nunito",
    "Oswald", "Source Sans 3", "Noto Sans", "Ubuntu", "Arimo", "PT Sans",
}
SHORTLIST = {"Serif": 45, "Sans Serif": 45, "Display": 35, "Handwriting": 12, "Monospace": 8}
CSS_FALLBACK = {"Serif": "serif", "Sans Serif": "sans-serif", "Display": "serif", "Handwriting": "cursive", "Monospace": "monospace"}

# Used when the catalogue can't be reached: (heading, body) by rough mood.
FALLBACK_PAIRS = [
    ("Fraunces", "Instrument Sans"),
    ("Space Grotesk", "IBM Plex Sans"),
    ("Cormorant Garamond", "Manrope"),
    ("DM Serif Display", "DM Sans"),
    ("Syne", "Work Sans"),
]
MAX_ICONS = 14

# Concepts nearly every small-business site needs, mapped to the glyph a designer would pick.
ICON_SYNONYMS = {
    "hour": "clock", "opening hour": "clock", "time": "clock", "timing": "clock",
    "location": "map-pin", "address": "map-pin", "direction": "map-pin", "visit": "map-pin",
    "review": "star", "rating": "star", "testimonial": "quote",
    "email": "mail", "e-mail": "mail", "call": "phone", "contact": "phone",
    "reservation": "calendar-check", "reserve": "calendar-check", "booking": "calendar-check", "appointment": "calendar-check",
    "delivery": "truck", "shipping": "truck", "price": "tag", "offer": "badge-percent",
    "food": "utensils", "restaurant": "utensils", "dining": "utensils", "gallery": "images",
    "team": "users", "award": "award", "quality": "badge-check", "secure": "shield-check",
}

_catalog: dict[str, dict] | None = None
_icons: dict[str, list[str]] | None = None
_lock = asyncio.Lock()


async def pick(brief: dict, description: str) -> dict:
    """Returns {heading, body, link, css, reason, icons: [{concept, name}], icon_script}."""
    catalog, icons = await _load()
    system = (
        f"{prompts.soul('fontknight')}\n\n"
        "Return ONLY a JSON object: "
        '{"heading": "family", "body": "family", "reason": "one sentence on why they fit", '
        '"icons": [{"concept": "what it shows", "keywords": ["1-3", "search", "words"]}]} '
        f"with 8-{MAX_ICONS} icons covering the site's sections (contact, hours, features, services, socials)."
    )
    shortlist = _shortlist(catalog) if catalog else {"pairs": [list(p) for p in FALLBACK_PAIRS]}
    context = {k: brief.get(k) for k in ("business", "industry", "audience", "tone", "style") if brief.get(k)}
    context["sections"] = [s.get("id") for s in brief.get("sections", []) if isinstance(s, dict)]
    user = (
        f"Website: {description}\nBrief: {json.dumps(context)}\n\n"
        f"Choose the heading and body families ONLY from this list of real Google Fonts:\n{json.dumps(shortlist)}"
    )
    try:
        data = parse_json(await llm.complete(system, user, "fontknight", 2000, json_mode=True))
    except (llm.LLMError, ValueError) as e:
        log.warning("font-knight model call failed: %s", e)
        data = {}

    heading, body = _resolve(catalog, data.get("heading"), "heading"), _resolve(catalog, data.get("body"), "body")
    if not heading or not body or heading == body:
        heading, body = FALLBACK_PAIRS[0]
    picked_icons = _search_icons(icons, data.get("icons") or []) if icons else []
    return {
        "heading": heading,
        "body": body,
        "reason": str(data.get("reason") or "")[:200],
        "link": _css_url(catalog, heading, body),
        "css": {
            "heading": f"'{heading}', {CSS_FALLBACK.get((catalog or {}).get(heading, {}).get('category'), 'serif')}",
            "body": f"'{body}', {CSS_FALLBACK.get((catalog or {}).get(body, {}).get('category'), 'sans-serif')}",
        },
        "icons": picked_icons,
        "icon_script": LUCIDE_SCRIPT if picked_icons else "",
    }


def notes_for_prompt(picked: dict) -> str:
    lines = [
        "Typography and icons from font-knight (use exactly these, do not substitute):",
        f'- Load: <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="{picked["link"]}" rel="stylesheet">',
        f"- Tailwind fontFamily: display: [{picked['css']['heading']}] for headings, sans: [{picked['css']['body']}] for everything else.",
    ]
    if picked.get("icons"):
        names = ", ".join(f'{i["name"]} ({i["concept"]})' for i in picked["icons"])
        lines += [
            f'- Icons are Lucide: add <script src="{picked["icon_script"]}"></script> in <head>, write icons as '
            '<i data-lucide="name" class="w-5 h-5" aria-hidden="true"></i>, and call lucide.createIcons() in the inline script at the end of <body>.',
            f"- Only these icon names exist for this site: {names}.",
            "- Lucide has no brand logos: for Instagram, Facebook or WhatsApp use a small inline SVG or a plain text link.",
        ]
    return "\n".join(lines)


def summary(picked: dict) -> str:
    text = f"Font Knight paired {picked['heading']} with {picked['body']}"
    if picked.get("icons"):
        text += f" and found {len(picked['icons'])} icons"
    return text + (f". {picked['reason']}" if picked.get("reason") else "")


# ---------------------------------------------------------------------------
# Catalogues
# ---------------------------------------------------------------------------

async def _load() -> tuple[dict | None, dict | None]:
    global _catalog, _icons
    async with _lock:
        if _catalog is None:
            _catalog = await _cached("fonts.json", CATALOG_URL, _compact_catalog)
        if _icons is None:
            _icons = await _cached(f"lucide-{LUCIDE_VERSION}.json", LUCIDE_TAGS_URL, lambda raw: json.loads(raw))
    return _catalog or None, _icons or None


async def _cached(name: str, url: str, parse) -> dict:
    path = CACHE_DIR / name
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            pass
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
        r.raise_for_status()
        data = parse(r.text)
    except (httpx.HTTPError, ValueError) as e:
        log.warning("could not load %s: %s", url, e)
        return {}
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def _compact_catalog(raw: str) -> dict:
    data = json.loads(raw.removeprefix(")]}'"))
    out = {}
    for f in data["familyMetadataList"]:
        if f.get("isNoto") or "latin" not in f.get("subsets", []):
            continue
        weights = sorted({int(k.rstrip("i")) for k in f.get("fonts", {}) if k.rstrip("i").isdigit()})
        out[f["family"]] = {"category": f["category"], "popularity": f.get("popularity", 9999), "weights": weights}
    return out


def _shortlist(catalog: dict) -> dict:
    """Popular families per category, minus the overused defaults."""
    by_category: dict[str, list[tuple[int, str]]] = {}
    for family, info in catalog.items():
        if family in OVERUSED or info["category"] not in SHORTLIST:
            continue
        # Body text needs a regular and a bold; display faces may be single-weight.
        if info["category"] in ("Serif", "Sans Serif") and not {400, 700} <= set(info["weights"]):
            continue
        by_category.setdefault(info["category"], []).append((info["popularity"], family))
    return {cat: [f for _, f in sorted(items)[: SHORTLIST[cat]]] for cat, items in by_category.items()}


def _resolve(catalog: dict | None, name, role: str) -> str:
    name = str(name or "").strip()
    if not name:
        return ""
    if not catalog:
        known = {f for pair in FALLBACK_PAIRS for f in pair}
        return name if name in known else ""
    lookup = {f.lower(): f for f in catalog}
    family = lookup.get(name.lower(), "")
    if family and role == "body" and catalog[family]["category"] in ("Display", "Handwriting"):
        return ""  # unreadable at paragraph size
    return family


def _css_url(catalog: dict | None, heading: str, body: str) -> str:
    def spec(family: str, wanted: tuple[int, ...]) -> str:
        weights = (catalog or {}).get(family, {}).get("weights") or list(wanted)
        chosen = [w for w in wanted if w in weights] or weights[:1]
        return f"family={quote_plus(family)}:wght@{';'.join(map(str, chosen))}"
    return f"https://fonts.googleapis.com/css2?{spec(heading, (400, 500, 600, 700, 800))}&{spec(body, (400, 500, 600, 700))}&display=swap"


def _search_icons(icons: dict[str, list[str]], wanted: list) -> list[dict]:
    """Best Lucide name per concept: synonyms, then exact names, then name parts, then tags."""
    found, used = [], set()
    for item in wanted[:MAX_ICONS]:
        if not isinstance(item, dict):
            continue
        concept = str(item.get("concept") or "").strip()
        phrases = [str(k).lower().strip() for k in (item.get("keywords") or []) if str(k).strip()] + [concept.lower()]
        best, best_score = None, 0.0
        for name, tags in icons.items():
            if name in used:
                continue
            parts = name.split("-")
            score = 0.0
            for rank, phrase in enumerate(phrases):
                weight = 1.0 / (1 + rank * 0.4)
                words = [_singular(w) for w in re.findall(r"[a-z0-9]+", phrase)]
                if ICON_SYNONYMS.get(phrase) == name or any(ICON_SYNONYMS.get(w) == name for w in words):
                    score += 8 * weight
                if "-".join(words) == name:
                    score += 6 * weight
                score += sum(3 * weight for w in words if w in parts)
                score += sum(1.5 * weight for w in words if w in tags)
            # Shorter names are the base glyph ("coffee" over "coffee-off").
            score -= 0.1 * len(parts)
            if parts[-1] in ("off", "x", "slash", "minus"):
                score -= 2
            if score > best_score:
                best, best_score = name, score
        if best and best_score >= 1:
            used.add(best)
            found.append({"concept": concept or best, "name": best})
    return found


def _singular(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word
