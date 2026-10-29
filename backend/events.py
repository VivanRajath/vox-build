"""In-process pub/sub that fans project events out to SSE subscribers."""
import asyncio
import json
from collections import defaultdict

_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)


def publish(project_id: str, event: dict) -> None:
    for queue in list(_subscribers.get(project_id, ())):
        queue.put_nowait(event)


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
