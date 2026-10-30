"""In-process pub/sub that fans project events out to SSE subscribers."""
import asyncio
import json
from collections import defaultdict

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

# The latest job per project, so the voice agent can ask how a background build is going.
_jobs: dict[str, dict] = {}


def publish(project_id: str, event: dict) -> None:
    _track(project_id, event)
    for queue in list(_subscribers.get(project_id, ())):
        queue.put_nowait(event)


def job(project_id: str) -> dict | None:
    return _jobs.get(project_id)


def _track(project_id: str, event: dict) -> None:
    kind = event.get("type")
    if kind == "job_started":
        _jobs[project_id] = {"state": "working", "instruction": event.get("instruction", ""), "stage": event.get("tier")}
    elif project_id not in _jobs:
        return
    elif kind in ("job_stage", "job_escalated"):
        _jobs[project_id]["stage"] = event.get("tier")
    elif kind == "job_done":
        _jobs[project_id].update(state="done", summary=event["version"].get("summary", ""))
    elif kind == "job_failed":
        _jobs[project_id].update(state="failed", reason=event.get("reason", ""))


async def stream(project_id: str):
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers[project_id].add(queue)
    try:
        yield "retry: 2000\n\n"
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        _subscribers[project_id].discard(queue)
        if not _subscribers[project_id]:
            _subscribers.pop(project_id, None)
