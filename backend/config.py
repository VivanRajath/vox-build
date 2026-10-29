import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data" / "projects"))
USERS_DIR = Path(os.getenv("USERS_DIR", DATA_DIR.parent / "users"))
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"


def _session_secret() -> str:
    """Signs session cookies and encrypts stored tokens/keys. Without an env
    value, a random one is kept on disk so restarts don't log everyone out."""
    explicit = os.getenv("SESSION_SECRET", "")
    if explicit:
        return explicit
    path = DATA_DIR.parent / ".session_secret"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    value = secrets.token_urlsafe(48)
    path.write_text(value, encoding="utf-8")
    return value


SESSION_SECRET = _session_secret()

# OAuth apps. Callback URLs: <site>/auth/google/callback and <site>/auth/github/callback
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")

# Bolna
BOLNA_API_KEY = os.getenv("BOLNA_API_KEY", "")
BOLNA_AGENT_ID = os.getenv("BOLNA_AGENT_ID", "")
BOLNA_API_BASE = os.getenv("BOLNA_API_BASE", "https://api.bolna.ai")

# Shared secret Bolna sends (as "Authorization: Bearer <secret>") when it
# calls our custom-function endpoints. Empty disables the check (local dev).
TOOL_SECRET = os.getenv("TOOL_SECRET", "")

# Public URL Bolna uses to reach this backend. Render sets RENDER_EXTERNAL_URL itself.
PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")

# How long a voice tool call waits for an edit before answering
# "still working" and letting the edit finish in the background.
TOOL_SYNC_WAIT = float(os.getenv("TOOL_SYNC_WAIT", "8"))

# LLM provider: "anthropic", "openai", "gemini" or "groq". Auto-detected from keys.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ENV_KEYS = {"anthropic": ANTHROPIC_API_KEY, "openai": OPENAI_API_KEY, "gemini": GEMINI_API_KEY, "groq": GROQ_API_KEY}

# Optional: better stock photos for the researcher (free key at pexels.com/api).
# Without it, photos come from Wikimedia Commons.
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")


def _detect_provider() -> str:
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if OPENAI_API_KEY:
        return "openai"
    if GEMINI_API_KEY:
        return "gemini"
    if GROQ_API_KEY:
        return "groq"
    return "none"


LLM_PROVIDER = _detect_provider()

# Tier -> model per provider. jnr = fast/cheap, snr = standard, architect = top.
DEFAULT_MODELS = {
    "anthropic": {"jnr": "claude-haiku-5-5", "snr": "claude-sonnet-5-5", "architect": "claude-opus-5-5"},
    "openai": {"jnr": "gpt-4.1-mini", "snr": "gpt-4.1", "architect": "gpt-4.1"},
    "gemini": {"jnr": "gemini-2.5-flash", "snr": "gemini-2.5-pro", "architect": "gemini-2.5-pro"},
    "groq": {"jnr": "qwen/qwen3.8-27b", "snr": "openai/gpt-oss-120b", "architect": "openai/gpt-oss-120b"},
}

# Tried in order when a model is rate limited. Groq's per-model token quotas
# are small on the free tier, so spilling over to a sibling model keeps a
# live demo going instead of stalling.
RATE_LIMIT_FALLBACKS = {
    "groq": ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"],
}


def model_for(tier: str) -> str:
    override = os.getenv(f"MODEL_{tier.upper()}")
    if override:
        return override
    if tier == "research":
        # The researcher runs on the fast model (its own rate-limit quota on Groq).
        return model_for("jnr")
    return DEFAULT_MODELS.get(LLM_PROVIDER, {}).get(tier, "")
