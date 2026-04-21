import asyncio
import hashlib
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.modules.display.routes import build_display_payload
from app.modules.kitchen.routes import build_kitchen_payload

router = APIRouter()


def _hash_payload(payload: object) -> str:
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha1(compact.encode("utf-8")).hexdigest()


async def _event_stream(payload_builder, event_name: str):
    last_revision = None

    while True:
        payload = payload_builder()
        revision = _hash_payload(payload)

        if revision != last_revision:
            body = json.dumps({"revision": revision, "payload": payload}, ensure_ascii=False)
            yield f"event: {event_name}\ndata: {body}\n\n"
            last_revision = revision
        else:
            yield "event: heartbeat\ndata: {}\n\n"

        await asyncio.sleep(1.0)


@router.get('/api/events/kitchen')
async def kitchen_events():
    return StreamingResponse(
        _event_stream(build_kitchen_payload, 'kitchen_update'),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


@router.get('/api/events/display')
async def display_events():
    return StreamingResponse(
        _event_stream(build_display_payload, 'display_update'),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )
