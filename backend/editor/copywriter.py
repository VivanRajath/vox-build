"""copywriter: writes the words for a new site before the architect lays it out.

Specific copy (real dish names, prices, hours, a voice that fits the brief) is
most of what separates a designed site from a template, and asking for it
separately keeps the architect's budget for layout.
"""
import json
import logging

from .. import llm
from . import prompts
from .research import parse_json

log = logging.getLogger("vox-build.copywriter")

COPY_SHAPE = """{
  "headline": "hero headline, under 9 words",
  "subheadline": "one or two sentences under the headline",
  "primary_cta": "button label", "secondary_cta": "button label",
  "sections": [{"id": "matches a brief section id", "eyebrow": "2-4 word label", "heading": "section heading",
                "body": "1-3 sentences", "items": [{"title": "", "text": "", "meta": "price, date, role or empty"}]}],
  "footer": "one closing line"
}"""


async def write(brief: dict, description: str) -> dict:
    system = (
        f"{prompts.soul('copywriter')}\n\nReturn ONLY a JSON object with this shape, one entry per brief section, "
        f"items only where the section lists things (menu, services, team, reviews, plans, FAQ):\n{COPY_SHAPE}"
    )
    context = {k: brief.get(k) for k in ("business", "industry", "audience", "tone", "sections") if brief.get(k)}
    try:
        raw = await llm.complete(system, f"Website: {description}\nBrief: {json.dumps(context)}", "copywriter", 4000, json_mode=True)
        data = parse_json(raw)
    except (llm.LLMError, ValueError) as e:
        log.warning("copywriter failed: %s", e)
        return {}
    return data if data.get("headline") else {}


def notes_for_prompt(copy: dict) -> str:
    return (
        "Copy from the copywriter. Use it as written (trim only to fit the layout); "
        "write anything missing in the same voice:\n" + json.dumps(copy, indent=1, ensure_ascii=False)
    )


def summary(copy: dict) -> str:
    return f'Copywriter wrote the headline "{copy["headline"]}" and copy for {len(copy.get("sections", []))} sections'
