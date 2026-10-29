"""researcher: plans a site before it is built and finds real photos for it.

brief()        LLM design brief: audience, tone, palette, fonts, sections, image slots
image_needs()  LLM picks image slots for an edit that mentions pictures
find_images()  searches Pexels (if PEXELS_API_KEY) or Wikimedia Commons and
               downloads the best match into the site's images/ folder
"""
import asyncio
import hashlib
import json
import logging
import re

import httpx

from .. import config, llm, store
from . import prompts

log = logging.getLogger("voicesite.research")

# Wikimedia requires an identifying User-Agent (https://w.wiki/4wJS).
USER_AGENT = "VoiceSite/1.0 (https://github.com/VivanRajath/repo-sanbox-agent) python-httpx"
WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
PEXELS_API = "https://api.pexels.com/v1/search"

IMAGE_WORDS = ("image", "photo", "picture", "pic ", "pics", "gallery", "background", "banner", "illustration")
SKIP_TITLE_WORDS = ("logo", "map", "diagram", "flag", "chart", "icon", "coat of arms", "seal", "svg", "drawing")
MAX_IMAGES = 6

BRIEF_SHAPE = """{
  "business": "name of the business or person",
  "industry": "short industry label",
  "audience": "who the site is for",
  "tone": "3-5 words describing voice and mood",
  "palette": {"primary": "#hex", "secondary": "#hex", "accent": "#hex", "background": "#hex", "text": "#hex"},
  "fonts": {"heading": "Google Font family", "body": "Google Font family"},
  "sections": [{"id": "hero", "purpose": "what it achieves", "elements": ["concrete element", "..."]}],
  "images": [{"slot": "hero", "query": "2-4 word photo search query", "fallback": "1-2 word generic subject", "alt": "alt text"}]
}"""


async def brief(description: str) -> dict:
    system = (
        f"{prompts.soul('research')}\n\nReturn ONLY a JSON object with this shape (5-8 sections, "
        f"3-{MAX_IMAGES} images, slot names are short lowercase ids):\n{BRIEF_SHAPE}"
    )
    try:
        raw = await llm.complete(system, f"Website description: {description}", "research", 3000)
        data = _parse_json(raw)
    except (llm.LLMError, ValueError) as e:
        log.warning("design brief failed: %s", e)
        return {}
    data["images"] = [i for i in data.get("images", []) if isinstance(i, dict) and i.get("query")][:MAX_IMAGES]
    return data


def wants_images(instruction: str) -> bool:
    text = f"{instruction.lower()} "
    return any(word in text for word in IMAGE_WORDS)


async def image_needs(instruction: str, brief_data: dict | None) -> list[dict]:
    context = f"The site is for: {brief_data.get('business')} ({brief_data.get('industry')}).\n" if brief_data else ""
    system = (
        f"{prompts.soul('research')}\n\nThe user asked for a change that needs photos. Return ONLY a JSON object "
        '{"images": [{"slot": "short-id", "query": "2-4 word photo search query", '
        '"fallback": "1-2 word generic subject", "alt": "alt text"}]} '
        "with 1-4 images, or an empty list if no new photos are needed."
    )
    try:
        raw = await llm.complete(system, f"{context}Requested change: {instruction}", "research", 1500)
        items = _parse_json(raw).get("images", [])
    except (llm.LLMError, ValueError) as e:
        log.warning("image planning failed: %s", e)
        return []
    return [i for i in items if isinstance(i, dict) and i.get("query")][:4]


async def find_images(project_id: str, needs: list[dict]) -> list[dict]:
    """Returns [{slot, path, alt, credit, source}] for every need that found a photo."""
    if not needs:
        return []
    images_dir = store.site_dir(project_id) / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=12, follow_redirects=True) as client:
        results = await asyncio.gather(*(_find_one(client, images_dir, need) for need in needs), return_exceptions=True)
    found = []
    for need, result in zip(needs, results):
        if isinstance(result, Exception):
            log.warning("image search failed for %r: %s", need.get("query"), result)
        elif result:
            found.append(result)
    return found


def notes_for_prompt(brief_data: dict | None, images: list[dict]) -> str:
    """Research notes appended to the developer prompt."""
    parts = []
    if brief_data:
        compact = {k: brief_data[k] for k in ("business", "industry", "audience", "tone", "palette", "fonts", "sections") if k in brief_data}
        parts.append("Design brief from the researcher (follow it):\n" + json.dumps(compact, indent=1))
    if images:
        lines = [f'- {img["slot"]}: src="{img["path"]}" alt="{img["alt"]}"' for img in images]
        credits = "; ".join(f'{img["credit"]} ({img["source"]})' for img in images)
        parts.append(
            "Photos found by the researcher. Use these exact relative src paths in the matching places, "
            "with object-cover so they crop nicely:\n" + "\n".join(lines) +
            f"\nAdd a small, subtle 'Photo credits' line in the footer: {credits}"
        )
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

async def _find_one(client: httpx.AsyncClient, images_dir, need: dict) -> dict | None:
    query = str(need["query"]).strip()
    queries = [query] + [q for q in [str(need.get("fallback") or "").strip()] if q and q.lower() != query.lower()]
    candidate = None
    for q in queries:
        if config.PEXELS_API_KEY:
            candidate = await _search_pexels(client, q)
        if not candidate:
            candidate = await _search_wikimedia(client, q)
        if candidate:
            break
    if not candidate:
        return None

    r = await client.get(candidate["url"])
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        return None
    ext = ".png" if "png" in r.headers["content-type"] else ".jpg"
    slot = re.sub(r"[^a-z0-9-]+", "-", str(need.get("slot", "image")).lower()).strip("-") or "image"
    name = f"{slot}-{hashlib.sha1(candidate['url'].encode()).hexdigest()[:6]}{ext}"
    (images_dir / name).write_bytes(r.content)
    return {
        "slot": slot,
        "path": f"images/{name}",
        "alt": str(need.get("alt") or query),
        "credit": candidate["credit"],
        "source": candidate["source"],
    }


async def _search_pexels(client: httpx.AsyncClient, query: str) -> dict | None:
    r = await client.get(
        PEXELS_API,
        params={"query": query, "per_page": 5, "orientation": "landscape"},
        headers={"Authorization": config.PEXELS_API_KEY},
    )
    if r.status_code != 200:
        return None
    photos = r.json().get("photos", [])
    if not photos:
        return None
    photo = photos[0]
    return {"url": photo["src"]["large2x"], "credit": f"Photo by {photo['photographer']} on Pexels", "source": photo["url"]}


async def _search_wikimedia(client: httpx.AsyncClient, query: str) -> dict | None:
    r = await client.get(WIKIMEDIA_API, params={
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": 10,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1280,
    })
    if r.status_code != 200:
        return None
    pages = r.json().get("query", {}).get("pages", {}).values()
    best, best_score = None, -1.0
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        title = page.get("title", "").lower()
        width, height = info.get("width", 0), info.get("height", 0)
        if not info.get("thumburl") or info.get("mime") not in ("image/jpeg", "image/png") or width < 800:
            continue
        if any(word in title for word in SKIP_TITLE_WORDS):
            continue
        # Prefer landscape photos, then earlier (more relevant) search hits.
        score = (1.0 if width >= height else 0.3) - 0.05 * page.get("index", 0)
        if score > best_score:
            best, best_score = (page, info), score
    if not best:
        return None
    page, info = best
    meta = info.get("extmetadata", {})
    artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip() or "Unknown"
    license_name = meta.get("LicenseShortName", {}).get("value", "")
    return {
        "url": info["thumburl"],
        "credit": f"{artist[:60]}, {license_name}, via Wikimedia Commons".replace(", ,", ","),
        "source": info.get("descriptionurl", ""),
    }


def _parse_json(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    data = json.loads(raw[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("model output is not a JSON object")
    return data
