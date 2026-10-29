"""Google and GitHub sign-in (OAuth 2.0 authorization code flow).

  /auth/{provider}/login     redirect to the provider (?next=/?p=<project>)
  /auth/{provider}/callback  exchange the code, sign in or link, redirect back
  /auth/logout

Signing in with GitHub, or connecting it while signed in with Google, asks
for the `repo` scope so sites can be pushed to the user's repositories.
"""
import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from . import config, users

log = logging.getLogger("voicesite.auth")
router = APIRouter()

PROVIDERS = {
    "google": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "scope": "openid email profile",
        "client": lambda: (config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET),
    },
    "github": {
        "authorize": "https://github.com/login/oauth/authorize",
        "token": "https://github.com/login/oauth/access_token",
        "scope": "repo read:user user:email",
        "client": lambda: (config.GITHUB_CLIENT_ID, config.GITHUB_CLIENT_SECRET),
    },
}


def enabled() -> dict[str, bool]:
    return {name: all(p["client"]()) for name, p in PROVIDERS.items()}


def current_user(request: Request) -> dict | None:
    return users.get(request.session.get("uid"))


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Sign in first")
    return user


def _provider(name: str) -> dict:
    if name not in PROVIDERS:
        raise HTTPException(404)
    if not enabled()[name]:
        raise HTTPException(503, f"{name.title()} sign-in is not configured")
    return PROVIDERS[name]


def _safe_next(value: str | None) -> str:
    # Only same-site paths, so the login can't bounce users to another site.
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value
    return "/"


def _callback_url(request: Request, name: str) -> str:
    return str(request.url_for("oauth_callback", provider=name))


@router.get("/auth/{provider}/login")
async def oauth_login(provider: str, request: Request, next: str = "/"):
    p = _provider(provider)
    state = secrets.token_urlsafe(24)
    request.session["oauth"] = {"state": state, "provider": provider, "next": _safe_next(next)}
    params = {
        "client_id": p["client"]()[0],
        "redirect_uri": _callback_url(request, provider),
        "response_type": "code",
        "scope": p["scope"],
        "state": state,
    }
    if provider == "google":
        params["prompt"] = "select_account"
    return RedirectResponse(f"{p['authorize']}?{urlencode(params)}")


@router.get("/auth/{provider}/callback", name="oauth_callback")
async def oauth_callback(provider: str, request: Request, code: str = "", state: str = "", error: str = ""):
    p = _provider(provider)
    pending = request.session.pop("oauth", None) or {}
    next_url = pending.get("next", "/")
    if error:
        return RedirectResponse(next_url)
    if not code or pending.get("provider") != provider or not secrets.compare_digest(pending.get("state", ""), state):
        raise HTTPException(400, "Sign-in expired or was tampered with. Try again.")

    client_id, client_secret = p["client"]()
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            p["token"],
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": _callback_url(request, provider),
            },
        )
        token = r.json().get("access_token") if r.status_code == 200 else None
        if not token:
            log.warning("%s token exchange failed: %s %s", provider, r.status_code, r.text[:300])
            raise HTTPException(400, f"{provider.title()} sign-in failed")
        if provider == "google":
            ident, profile = await _google_profile(client, token)
        else:
            ident, profile = await _github_profile(client, token)

    user = current_user(request)
    if user:
        users.link_identity(user, provider, ident)
        users.save(user)
    else:
        user = users.login(provider, ident, profile)
    if provider == "github":
        users.set_github(user, profile["login"], token)
    request.session["uid"] = user["id"]
    return RedirectResponse(next_url)


async def _google_profile(client: httpx.AsyncClient, token: str) -> tuple[str, dict]:
    r = await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    info = r.json()
    return info["sub"], {"name": info.get("name"), "email": info.get("email"), "avatar": info.get("picture")}


async def _github_profile(client: httpx.AsyncClient, token: str) -> tuple[str, dict]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    r = await client.get("https://api.github.com/user", headers=headers)
    r.raise_for_status()
    info = r.json()
    email = info.get("email")
    if not email:
        emails = await client.get("https://api.github.com/user/emails", headers=headers)
        if emails.status_code == 200:
            email = next((e["email"] for e in emails.json() if e.get("primary") and e.get("verified")), None)
    profile = {"login": info["login"], "name": info.get("name") or info["login"], "email": email, "avatar": info.get("avatar_url")}
    return str(info["id"]), profile


@router.post("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}
