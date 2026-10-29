"""User accounts: OAuth identities, a linked GitHub token and per-user LLM settings.

data/users/<id>.json
  id, name, email, avatar, identities{"google": sub, "github": id}
  github{login, token*}    llm{provider, api_key*, base_url, models{jnr,snr,architect}}

* encrypted with a key derived from SESSION_SECRET, so a copied data folder
  doesn't leak tokens without the secret.
"""
import base64
import hashlib
import json
import re
import time
import uuid

from cryptography.fernet import Fernet, InvalidToken

from . import config

ID_RE = re.compile(r"^[a-f0-9]{32}$")
PROVIDERS = ("anthropic", "openai", "gemini", "groq", "custom")
TIERS = ("jnr", "snr", "architect")

_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(config.SESSION_SECRET.encode()).digest()))


def _encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def _decrypt(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _fernet.decrypt(value.encode()).decode()
    except InvalidToken:
        # SESSION_SECRET changed: the stored secret is unusable, act as if unset.
        return ""


def _path(user_id: str):
    return config.USERS_DIR / f"{user_id}.json"


def get(user_id: str | None) -> dict | None:
    if not ID_RE.match(user_id or ""):
        return None
    path = _path(user_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def save(user: dict) -> None:
    config.USERS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _path(user["id"]).with_suffix(".tmp")
    tmp.write_text(json.dumps(user, indent=2), encoding="utf-8")
    tmp.replace(_path(user["id"]))


def find_by_identity(provider: str, ident: str) -> dict | None:
    if not config.USERS_DIR.is_dir():
        return None
    for path in config.USERS_DIR.glob("*.json"):
        user = json.loads(path.read_text(encoding="utf-8"))
        if user.get("identities", {}).get(provider) == ident:
            return user
    return None


def login(provider: str, ident: str, profile: dict) -> dict:
    """Finds or creates the user for an OAuth identity and refreshes its profile."""
    user = find_by_identity(provider, ident)
    if user is None:
        user = {"id": uuid.uuid4().hex, "created": time.time(), "identities": {provider: ident}}
    for field in ("name", "email", "avatar"):
        if profile.get(field) and not (provider == "github" and user.get(field)):
            # Google's profile wins over GitHub's when both are linked.
            user[field] = profile[field]
    save(user)
    return user


def link_identity(user: dict, provider: str, ident: str) -> None:
    other = find_by_identity(provider, ident)
    if other and other["id"] != user["id"]:
        # The account was used on its own before; move it over to this user.
        other["identities"].pop(provider, None)
        if provider == "github":
            other.pop("github", None)
        save(other)
    user.setdefault("identities", {})[provider] = ident


def set_github(user: dict, login_name: str, token: str) -> None:
    user["github"] = {"login": login_name, "token": _encrypt(token), "linked": time.time()}
    save(user)


def github_token(user: dict | None) -> str:
    return _decrypt((user or {}).get("github", {}).get("token"))


def set_llm(user: dict, provider: str, api_key: str | None, base_url: str, models: dict) -> None:
    """api_key=None keeps the stored key (the browser never sees it again)."""
    current = user.get("llm") or {}
    if api_key is None and current.get("provider") == provider:
        encrypted = current.get("api_key")
    else:
        encrypted = _encrypt(api_key) if api_key else None
    user["llm"] = {
        "provider": provider,
        "api_key": encrypted,
        "key_hint": (f"…{api_key[-4:]}" if api_key else current.get("key_hint")) if encrypted else None,
        "base_url": base_url,
        "models": {t: str(models.get(t) or "").strip() for t in TIERS},
    }
    save(user)


def clear_llm(user: dict) -> None:
    user.pop("llm", None)
    save(user)


def llm_settings(user: dict | None) -> dict | None:
    """Decrypted settings for llm.use_settings, or None to use the server's .env."""
    s = (user or {}).get("llm")
    api_key = _decrypt((s or {}).get("api_key"))
    if not api_key:
        return None
    return {"provider": s["provider"], "api_key": api_key, "base_url": s.get("base_url", ""), "models": s.get("models", {})}


def public(user: dict | None) -> dict | None:
    """What the browser may see: no tokens, no keys."""
    if not user:
        return None
    s = user.get("llm")
    return {
        "id": user["id"],
        "name": user.get("name"),
        "email": user.get("email"),
        "avatar": user.get("avatar"),
        "github": {"login": user["github"]["login"]} if github_token(user) else None,
        "llm": {
            "provider": s["provider"],
            "base_url": s.get("base_url", ""),
            "models": s.get("models", {}),
            "key_hint": s.get("key_hint"),
            "has_key": bool(_decrypt(s.get("api_key"))),
        } if s else None,
    }
