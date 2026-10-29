"""On-disk project store with linear version history.

data/projects/<id>/
  meta.json        id, created, versions[], current, selection
  site/            the live site served to the preview
  history/<n>/     snapshot of site/ for version n
"""
import json
import re
import shutil
import time
import uuid
from pathlib import Path

from . import config

ID_RE = re.compile(r"^[a-f0-9]{8,32}$")

STARTER_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Your new website</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-50 text-slate-800 flex items-center justify-center">
  <main class="text-center px-6">
    <h1 class="text-4xl font-bold mb-4">Your website will appear here</h1>
    <p class="text-lg text-slate-500">Tap the mic and describe what you want to build.</p>
  </main>
</body>
</html>
"""


class ProjectNotFound(KeyError):
    pass


def _dir(project_id: str) -> Path:
    if not ID_RE.match(project_id or ""):
        raise ProjectNotFound(project_id)
    return config.DATA_DIR / project_id


def exists(project_id: str) -> bool:
    try:
        return (_dir(project_id) / "meta.json").is_file()
    except ProjectNotFound:
        return False


def create() -> dict:
    project_id = uuid.uuid4().hex[:12]
    root = _dir(project_id)
    (root / "site").mkdir(parents=True)
    (root / "site" / "index.html").write_text(STARTER_HTML, encoding="utf-8")
    meta = {"id": project_id, "created": time.time(), "versions": [], "current": 0, "selection": None}
    _snapshot(root, 0)
    meta["versions"].append({"n": 0, "summary": "Blank starter page", "instruction": "", "tier": "", "ts": time.time()})
    _save_meta(root, meta)
    return meta


def load_meta(project_id: str) -> dict:
    path = _dir(project_id) / "meta.json"
    if not path.is_file():
        raise ProjectNotFound(project_id)
    return json.loads(path.read_text(encoding="utf-8"))


def _save_meta(root: Path, meta: dict) -> None:
    tmp = root / "meta.json.tmp"
    tmp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    tmp.replace(root / "meta.json")


def site_dir(project_id: str) -> Path:
    return _dir(project_id) / "site"


def read_files(project_id: str) -> dict[str, str]:
    site = site_dir(project_id)
    return {
        p.relative_to(site).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(site.rglob("*"))
        if p.is_file() and p.suffix in (".html", ".css", ".js")
    }


def read_index(project_id: str) -> str:
    return (site_dir(project_id) / "index.html").read_text(encoding="utf-8")


def commit(project_id: str, files: dict[str, str], summary: str, instruction: str, tier: str) -> dict:
    """Write files into site/ and record a new version. Versions after the
    current one (i.e. undone ones) are discarded, like an editor's undo stack."""
    root = _dir(project_id)
    meta = load_meta(project_id)
    site = root / "site"
    for rel, content in files.items():
        target = (site / rel).resolve()
        if site.resolve() not in target.parents:
            raise ValueError(f"Refusing to write outside the site: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    for v in meta["versions"]:
        if v["n"] > meta["current"]:
            shutil.rmtree(root / "history" / str(v["n"]), ignore_errors=True)
    meta["versions"] = [v for v in meta["versions"] if v["n"] <= meta["current"]]

    n = meta["current"] + 1
    _snapshot(root, n)
    version = {"n": n, "summary": summary, "instruction": instruction, "tier": tier, "ts": time.time()}
    meta["versions"].append(version)
    meta["current"] = n
    _save_meta(root, meta)
    return version


def restore(project_id: str, n: int) -> dict:
    root = _dir(project_id)
    meta = load_meta(project_id)
    snap = root / "history" / str(n)
    if not snap.is_dir():
        raise ValueError(f"No version {n}")
    shutil.rmtree(root / "site")
    shutil.copytree(snap, root / "site")
    meta["current"] = n
    _save_meta(root, meta)
    return meta


def undo(project_id: str) -> dict | None:
    meta = load_meta(project_id)
    if meta["current"] <= 0:
        return None
    return restore(project_id, meta["current"] - 1)


def set_selection(project_id: str, selection: dict | None) -> None:
    root = _dir(project_id)
    meta = load_meta(project_id)
    meta["selection"] = selection
    _save_meta(root, meta)


def set_brief(project_id: str, brief: dict) -> None:
    """The researcher's design brief, reused by later edits for consistency."""
    root = _dir(project_id)
    meta = load_meta(project_id)
    meta["brief"] = brief
    _save_meta(root, meta)


def update(project_id: str, **fields) -> dict:
    """Sets top-level meta fields such as owner (user id) and github (last push target)."""
    root = _dir(project_id)
    meta = load_meta(project_id)
    meta.update(fields)
    _save_meta(root, meta)
    return meta


def export_files(project_id: str) -> dict[str, bytes]:
    """Every file of the live site, for the zip download and GitHub push."""
    site = site_dir(project_id)
    return {p.relative_to(site).as_posix(): p.read_bytes() for p in sorted(site.rglob("*")) if p.is_file()}


def _snapshot(root: Path, n: int) -> None:
    dest = root / "history" / str(n)
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(root / "site", dest)
