"""VoiceSite backend.

  /api/*      browser API (projects, typed commands, SSE, Bolna session mint,
              account + AI settings, zip download, GitHub push)
  /auth/*     Google / GitHub sign-in
  /tools/*    Bolna custom-function endpoints, called mid-conversation
  /preview/*  serves generated sites to the preview iframe
"""
import asyncio
import io
import ipaddress
import logging
import mimetypes
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import auth, config, events, github, llm, store, users
from .editor import engine

log = logging.getLogger("voicesite")
app = FastAPI(title="VoiceSite")
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET, session_cookie="voicesite", max_age=30 * 86400, same_site="lax")
app.include_router(auth.router)

INJECT_JS = Path(__file__).with_name("preview_inject.js")
NO_STORE = {"Cache-Control": "no-store"}
# Generated pages are untrusted (anyone with a project link can edit them) and
# share this origin with the session cookie. Sandboxing without allow-same-origin
# gives them an opaque origin, in the iframe and when opened directly, so their
# scripts can't call /api as the signed-in viewer (e.g. push to their GitHub).
PREVIEW_SANDBOX = "sandbox allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals allow-downloads"

# Project the most recent voice call was started for. Fallback for tool calls
# that arrive without a usable project_id.
_active_project: str | None = None
_background: set[asyncio.Task] = set()


def _spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)
    return task


def _require_project(project_id: str) -> dict:
    try:
        return store.load_meta(project_id)
    except store.ProjectNotFound:
        raise HTTPException(404, "Project not found")


def _claim(request: Request, meta: dict) -> None:
    """A signed-in user who works on an unowned project becomes its owner,
    so voice and typed edits run on their AI settings."""
    user = auth.current_user(request)
    if user and not meta.get("owner"):
        store.update(meta["id"], owner=user["id"])


def _run(project_id: str, coro) -> asyncio.Task:
    """Runs an edit job with the project owner's AI settings (or the server's .env)."""
    owner = users.get(store.load_meta(project_id).get("owner"))

    async def with_settings():
        llm.use_settings(users.llm_settings(owner))
        return await coro

    return _spawn(with_settings())


# ---------------------------------------------------------------------------
# Browser API
# ---------------------------------------------------------------------------

@app.get("/api/config")
async def get_config():
    return {
        "voice_enabled": bool(config.BOLNA_API_KEY and config.BOLNA_AGENT_ID),
        "llm_provider": config.LLM_PROVIDER,
        "auth": auth.enabled(),
        "default_models": config.DEFAULT_MODELS,
    }


@app.post("/api/projects")
async def create_project(request: Request):
    meta = store.create()
    _claim(request, meta)
    return store.load_meta(meta["id"])


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    return _require_project(project_id)


@app.post("/api/projects/{project_id}/command")
async def typed_command(project_id: str, request: Request):
    """Typed fallback for the voice flow. Runs in the background; results arrive over SSE."""
    meta = _require_project(project_id)
    text = str((await request.json()).get("text", "")).strip()
    if not text:
        raise HTTPException(400, "Empty command")
    _claim(request, meta)
    if text.lower() in ("undo", "undo that", "go back"):
        _spawn(engine.undo(project_id))
    elif meta["current"] == 0:
        _run(project_id, engine.generate(project_id, text))
    else:
        _run(project_id, engine.edit(project_id, text))
    return JSONResponse({"accepted": True}, status_code=202)


@app.post("/api/projects/{project_id}/undo")
async def undo(project_id: str):
    _require_project(project_id)
    return await engine.undo(project_id)


@app.post("/api/projects/{project_id}/restore/{n}")
async def restore(project_id: str, n: int):
    _require_project(project_id)
    try:
        return await engine.restore(project_id, n)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/api/projects/{project_id}/select")
async def select(project_id: str, request: Request):
    _require_project(project_id)
    selection = (await request.json()).get("selection")
    store.set_selection(project_id, selection)
    events.publish(project_id, {"type": "selection", "selection": selection})
    return {"ok": True}


@app.get("/api/projects/{project_id}/events")
async def project_events(project_id: str):
    _require_project(project_id)
    return StreamingResponse(
        events.stream(project_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/bolna-session")
async def bolna_session(request: Request):
    """Mints a single-use Bolna web-call session. The API key never leaves the server."""
    global _active_project
    if not (config.BOLNA_API_KEY and config.BOLNA_AGENT_ID):
        raise HTTPException(503, "Voice is not configured: set BOLNA_API_KEY and BOLNA_AGENT_ID")
    try:
        body = await request.json()
    except ValueError:
        body = {}
    user_data = body.get("user_data") or {}
    project_id = str(user_data.get("project_id", ""))
    if store.exists(project_id):
        _active_project = project_id
        _claim(request, store.load_meta(project_id))

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"{config.BOLNA_API_BASE}/web-call/session",
            headers={"Authorization": f"Bearer {config.BOLNA_API_KEY}"},
            json={"agent_id": config.BOLNA_AGENT_ID, "user_data": user_data},
        )
    if r.status_code >= 400:
        log.warning("Bolna session mint failed: %s %s", r.status_code, r.text[:300])
    return Response(content=r.content, status_code=r.status_code, media_type="application/json")


@app.get("/api/projects/{project_id}/download")
async def download(project_id: str):
    meta = _require_project(project_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, data in store.export_files(project_id).items():
            zf.writestr(rel, data)
    name = _slug((meta.get("brief") or {}).get("business", "")) or f"site-{project_id}"
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}.zip"', **NO_STORE},
    )


@app.post("/api/projects/{project_id}/github")
async def push_to_github(project_id: str, request: Request):
    meta = _require_project(project_id)
    user = auth.require_user(request)
    token = users.github_token(user)
    if not token:
        raise HTTPException(403, "Connect your GitHub account first")
    body = await request.json()
    files = store.export_files(project_id)
    business = (meta.get("brief") or {}).get("business") or "My website"
    files.setdefault("README.md", f"# {business}\n\nBuilt by voice with VoiceSite. Open `index.html` in a browser to view it.\n".encode())
    version = next((v for v in meta["versions"] if v["n"] == meta["current"]), {})
    try:
        result = await github.push(
            token,
            str(body.get("repo", "")),
            files,
            message=f"VoiceSite v{meta['current']}: {version.get('summary') or 'Update site'}",
            private=bool(body.get("private", False)),
            description=f"{business} website, built with VoiceSite",
        )
    except github.GitHubError as e:
        raise HTTPException(400, str(e))
    store.update(project_id, github={"repo": result["repo"], "url": result["url"]})
    return result


def _slug(text: str) -> str:
    return "-".join("".join(c if c.isalnum() else " " for c in text.lower()).split())[:60]


# ---------------------------------------------------------------------------
# Account + AI settings
# ---------------------------------------------------------------------------

@app.get("/api/me")
async def me(request: Request):
    return {"user": users.public(auth.current_user(request))}


def _check_base_url(provider: str, base_url: str) -> str:
    if provider != "custom":
        return ""
    url = urlparse(base_url.strip())
    if url.scheme != "https" or not url.hostname:
        raise HTTPException(400, "Base URL must be an https:// URL")
    host = url.hostname.lower()
    try:
        private = not ipaddress.ip_address(host).is_global
    except ValueError:
        private = host == "localhost" or host.endswith((".local", ".internal", ".localhost"))
    if private:
        # The server makes these requests, so it must not be pointed at its own network.
        raise HTTPException(400, "Base URL must be a public address")
    return base_url.strip().rstrip("/")


def _llm_form(body: dict) -> tuple[str, str | None, str]:
    """(provider, api_key or None to reuse the stored one, base_url) from the settings form."""
    provider = str(body.get("provider", ""))
    if provider not in users.PROVIDERS:
        raise HTTPException(400, "Unknown provider")
    api_key = str(body.get("api_key") or "").strip() or None
    return provider, api_key, _check_base_url(provider, str(body.get("base_url", "")))


@app.put("/api/me/llm")
async def save_llm(request: Request):
    user = auth.require_user(request)
    body = await request.json()
    provider, api_key, base_url = _llm_form(body)
    stored = users.llm_settings(user)
    if not api_key and not (stored and stored["provider"] == provider):
        raise HTTPException(400, "Add an API key for this provider")
    models = body.get("models") or {}
    if provider == "custom" and not all(str(models.get(t) or "").strip() for t in users.TIERS):
        raise HTTPException(400, "Custom providers need a model for every tier")
    users.set_llm(user, provider, api_key, base_url, models)
    return {"user": users.public(user)}


@app.delete("/api/me/llm")
async def clear_llm(request: Request):
    user = auth.require_user(request)
    users.clear_llm(user)
    return {"user": users.public(user)}


@app.post("/api/me/llm/models")
async def llm_models(request: Request):
    user = auth.require_user(request)
    provider, api_key, base_url = _llm_form(await request.json())
    if not api_key:
        stored = users.llm_settings(user)
        api_key = stored["api_key"] if stored and stored["provider"] == provider else None
    if not api_key:
        raise HTTPException(400, "Enter an API key first")
    try:
        return {"models": await llm.list_models(provider, api_key, base_url)}
    except llm.LLMError as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------------------
# Bolna custom functions
# ---------------------------------------------------------------------------

async def _tool_args(request: Request) -> dict:
    if config.TOOL_SECRET and request.headers.get("authorization") != f"Bearer {config.TOOL_SECRET}":
        raise HTTPException(401, "Bad tool secret")
    args = dict(request.query_params)
    try:
        body = await request.json()
        if isinstance(body, dict):
            args.update(body)
    except ValueError:
        pass
    log.info("tool call %s %s", request.url.path, {k: str(v)[:120] for k, v in args.items()})
    return args


def _tool_project(args: dict) -> str:
    project_id = str(args.get("project_id") or "").strip()
    if store.exists(project_id):
        return project_id
    if _active_project and store.exists(_active_project):
        return _active_project
    raise HTTPException(404, "No active website project")


async def _answer_voice(project_id: str, coro) -> dict:
    """Waits briefly so quick edits can be confirmed in the same breath;
    otherwise lets the edit finish in the background (the preview updates via SSE)."""
    task = _run(project_id, coro)
    try:
        result = await asyncio.wait_for(asyncio.shield(task), config.TOOL_SYNC_WAIT)
    except asyncio.TimeoutError:
        return {"status": "in_progress", "message": "Working on it. The change will show up on screen in a few seconds."}
    return {"status": "done" if result["ok"] else "failed", "message": result["message"]}


@app.post("/tools/generate_site")
async def tool_generate_site(request: Request):
    args = await _tool_args(request)
    project_id = _tool_project(args)
    description = str(args.get("description", "")).strip()
    if not description:
        return {"status": "failed", "message": "I need a short description of the website first."}
    return await _answer_voice(project_id, engine.generate(project_id, description))


@app.post("/tools/edit_site")
async def tool_edit_site(request: Request):
    args = await _tool_args(request)
    project_id = _tool_project(args)
    instruction = str(args.get("instruction", "")).strip()
    if not instruction:
        return {"status": "failed", "message": "What would you like me to change?"}
    if store.load_meta(project_id)["current"] == 0:
        return await _answer_voice(project_id, engine.generate(project_id, instruction))
    return await _answer_voice(project_id, engine.edit(project_id, instruction))


@app.post("/tools/undo_change")
async def tool_undo(request: Request):
    project_id = _tool_project(await _tool_args(request))
    result = await engine.undo(project_id)
    return {"status": "done" if result["ok"] else "failed", "message": result["message"]}


@app.post("/tools/describe_site")
async def tool_describe(request: Request):
    project_id = _tool_project(await _tool_args(request))
    return {"status": "done", "message": engine.describe(project_id)}


# ---------------------------------------------------------------------------
# Preview + frontend
# ---------------------------------------------------------------------------

@app.get("/preview-inject.js")
async def preview_inject():
    return FileResponse(INJECT_JS, media_type="application/javascript", headers=NO_STORE)


@app.get("/preview/{project_id}/{path:path}")
async def preview(project_id: str, path: str = ""):
    _require_project(project_id)
    site = store.site_dir(project_id).resolve()
    target = (site / (path or "index.html")).resolve()
    if target != site and site not in target.parents:
        raise HTTPException(404)
    if target.is_dir():
        target = target / "index.html"
    if not target.is_file():
        raise HTTPException(404)
    if target.suffix == ".html":
        html = target.read_text(encoding="utf-8")
        tag = '<script src="/preview-inject.js"></script>'
        idx = html.lower().rfind("</body>")
        html = html[:idx] + tag + html[idx:] if idx != -1 else html + tag
        return Response(html, media_type="text/html", headers={**NO_STORE, "Content-Security-Policy": PREVIEW_SANDBOX})
    media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return FileResponse(target, media_type=media_type, headers=NO_STORE)


if config.FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="frontend")
