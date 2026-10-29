"""intent-router: classifies a voice edit into a tier.

Runs on keywords rather than an LLM call because every extra round trip is
dead air on a voice call. Misroutes are cheap: a jnr/snr patch that fails to
apply escalates to the next tier automatically (see engine.py).
"""

ARCHITECT_KEYWORDS = [
    "redesign", "start over", "from scratch", "completely", "whole site", "entire site",
    "whole page", "entire page", "rebuild", "overhaul", "restructure", "new layout",
    "different style", "change the theme", "new theme", "make it look like", "dark mode",
    "light mode", "rewrite",
]

SNR_KEYWORDS = [
    "add a", "add an", "add some", "add section", "new section", "create", "insert",
    "gallery", "form", "testimonial", "pricing", "faq", "footer", "navbar", "nav bar",
    "menu", "remove the", "delete", "get rid of", "move", "reorder", "swap", "animation",
    "animate", "carousel", "slider", "map", "contact", "button that", "link to", "every",
    "all the", "each",
]


def route(instruction: str) -> str:
    text = instruction.lower()
    if any(kw in text for kw in ARCHITECT_KEYWORDS):
        return "architect"
    if any(kw in text for kw in SNR_KEYWORDS) or len(text.split()) > 25:
        return "snr"
    return "jnr"


ESCALATION = {"jnr": "snr", "snr": "architect", "architect": None}
