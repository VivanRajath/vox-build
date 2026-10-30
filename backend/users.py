"""User accounts: OAuth identities, a linked GitHub token and per-user AI settings.

data/users/<id>.json
  id, name, email, avatar, identities{"google": sub, "github": id}, guest?
  github{login, token*}
  ai{keys[{id, provider, label, api_key*, base_url, hint}],
     models{jnr|snr|architect: {provider, model}}, pexels*}

* encrypted with a key derived from SESSION_SECRET, so a copied data folder
  doesn't leak tokens without the secret.

Guests are accounts without a sign-in identity, created for a browser so it
can keep its own API keys. Signing in later turns the guest into a full account.
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


def create_guest() -> dict:
    user = {"id": uuid.uuid4().hex, "created": time.time(), "identities": {}, "guest": True, "name": "Guest"}
    save(user)
    return user


def promote_guest(user: dict, profile: dict) -> None:
    """A guest who signs in keeps their keys and projects under the new identity."""
    user.pop("guest", None)
    for field in ("name", "email", "avatar"):
        if profile.get(field):
            user[field] = profile[field]


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


# ---------------------------------------------------------------------------
# AI settings: any number of keys, a provider + model per tier, a Pexels key
# ---------------------------------------------------------------------------

def _hint(secret: str) -> str:
    return f"...{secret[-4:]}" if len(secret) > 8 else "saved"


def _ai(user: dict) -> dict:
    """The user's AI settings, upgrading the old single-key `llm` shape on the fly."""
    ai = user.setdefault("ai", {"keys": [], "models": {}, "pexels": None})
    old = user.pop("llm", None)
    if old and old.get("api_key"):
        ai["keys"].append({
            # Fixed id: the migration repeats on every load until the user is saved.
            "id": "migrated", "provider": old["provider"], "label": "",
            "api_key": old["api_key"], "base_url": old.get("base_url", ""), "hint": old.get("key_hint") or "saved",
        })
        for tier, model in (old.get("models") or {}).items():
            if model:
                ai["models"][tier] = {"provider": old["provider"], "model": model}
    return ai


def add_key(user: dict, provider: str, api_key: str, base_url: str, label: str) -> dict:
    ai = _ai(user)
    entry = {
        "id": uuid.uuid4().hex[:10], "provider": provider, "label": label.strip()[:40],
        "api_key": _encrypt(api_key), "base_url": base_url, "hint": _hint(api_key), "added": time.time(),
    }
    ai["keys"].append(entry)
    save(user)
    return entry


def remove_key(user: dict, key_id: str) -> bool:
    ai = _ai(user)
    before = len(ai["keys"])
    ai["keys"] = [k for k in ai["keys"] if k["id"] != key_id]
    save(user)
    return len(ai["keys"]) < before


def key_credentials(user: dict, key_id: str) -> tuple[str, str, str] | None:
    """(provider, api_key, base_url) for one stored key, to list its models."""
    for k in _ai(user)["keys"]:
        if k["id"] == key_id:
            api_key = _decrypt(k["api_key"])
            return (k["provider"], api_key, k.get("base_url", "")) if api_key else None
    return None


def set_models(user: dict, models: dict) -> None:
    ai = _ai(user)
    ai["models"] = {}
    for tier in TIERS:
        pick = models.get(tier) or {}
        provider, model = str(pick.get("provider") or ""), str(pick.get("model") or "").strip()
        if provider in PROVIDERS:
            ai["models"][tier] = {"provider": provider, "model": model}
    save(user)


def set_pexels(user: dict, api_key: str | None) -> None:
    _ai(user)["pexels"] = {"key": _encrypt(api_key), "hint": _hint(api_key)} if api_key else None
    save(user)


def ai_settings(user: dict | None) -> dict | None:
    """Decrypted settings for llm.use_settings, or None to use only the server's .env."""
    if not user:
        return None
    ai = _ai(user)
    keys: dict[str, list[dict]] = {}
    for k in ai["keys"]:
        api_key = _decrypt(k["api_key"])
        if api_key:
            keys.setdefault(k["provider"], []).append({"api_key": api_key, "base_url": k.get("base_url", "")})
    pexels = _decrypt((ai.get("pexels") or {}).get("key"))
    if not keys and not ai["models"] and not pexels:
        return None
    return {"keys": keys, "order": list(keys), "models": ai["models"], "pexels_key": pexels}


def ai_view(user: dict) -> dict:
    """AI settings as the browser may see them: hints, never keys."""
    ai = _ai(user)
    return {
        "keys": [
            {"id": k["id"], "provider": k["provider"], "label": k.get("label", ""), "hint": k.get("hint", ""), "base_url": k.get("base_url", "")}
            for k in ai["keys"]
        ],
        "models": ai["models"],
        "pexels": {"hint": ai["pexels"]["hint"]} if ai.get("pexels") else None,
    }


def public(user: dict | None) -> dict | None:
    """What the browser may see: no tokens, no keys."""
    if not user:
        return None
    ai = _ai(user)
    return {
        "id": user["id"],
        "name": user.get("name"),
        "email": user.get("email"),
        "avatar": user.get("avatar"),
        "guest": bool(user.get("guest")),
        "github": {"login": user["github"]["login"]} if github_token(user) else None,
        "ai": {"key_count": len(ai["keys"]), "providers": sorted({k["provider"] for k in ai["keys"]})},
    }
