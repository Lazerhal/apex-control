from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db, db_url, AsyncSessionLocal
from src.db.models import Event, Project
from src.api.schemas import EventCreate, EventResponse
from src.events import emit
import anyio
import asyncio
import asyncpg
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])

# Channel the database trigger on events notifies with the new row's id
NOTIFY_CHANNEL = "apex_events"
HEARTBEAT_SECONDS = 15
DB_TIMEOUT_SECONDS = 5
LISTEN_DSN = db_url.replace("postgresql+asyncpg://", "postgresql://")

async def _load_event_json(event_id: str) -> str | None:
    # Shielded so a client disconnect cannot interrupt a pooled connection mid-query
    with anyio.move_on_after(DB_TIMEOUT_SECONDS, shield=True):
        try:
            async with AsyncSessionLocal() as session:
                event = await session.get(Event, uuid.UUID(event_id))
            if event:
                return EventResponse.model_validate(event).model_dump_json()
        except Exception:
            logger.exception("Could not load event %s for the stream", event_id)
    return None

async def _sse_messages(queue: asyncio.Queue):
    yield ": connected\n\n"
    while True:
        try:
            event_id = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
        except asyncio.TimeoutError:
            yield ": heartbeat\n\n"
            continue
        if event_id is None:  # listener connection lost: end so the client reconnects
            return
        data = await _load_event_json(event_id)
        if data:
            yield f"id: {event_id}\ndata: {data}\n\n"

async def _close_listener(conn: asyncpg.Connection, callback) -> None:
    with anyio.move_on_after(DB_TIMEOUT_SECONDS, shield=True):
        try:
            if not conn.is_closed():
                await conn.remove_listener(NOTIFY_CHANNEL, callback)
                await conn.close()
        except Exception:
            logger.warning("Event stream listener did not close cleanly", exc_info=True)
    if not conn.is_closed():
        conn.terminate()

class _ListenerStreamingResponse(StreamingResponse):
    """Closes the listener however the response ends, including client disconnect."""

    def __init__(self, content, conn: asyncpg.Connection, callback, **kwargs):
        super().__init__(content, **kwargs)
        self.conn = conn
        self.callback = callback

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            await _close_listener(self.conn, self.callback)

@router.get("", response_model=list[EventResponse])
async def list_events(
    limit: int = Query(50, ge=1, le=500),
    kind: str | None = None,
    project_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Event)
    if kind:
        query = query.where(Event.kind == kind)
    if project_id:
        query = query.where(Event.project_id == project_id)
    result = await db.execute(query.order_by(Event.created_at.desc()).limit(limit))
    return result.scalars().all()

@router.get("/stream")
async def stream_events():
    """Server-Sent Events: each new event as JSON. Events missed while disconnected are not replayed."""
    queue: asyncio.Queue = asyncio.Queue()

    def on_notify(conn, pid, channel, payload):
        queue.put_nowait(payload)

    conn = None
    try:
        # A dedicated connection: LISTEN has to hold it for the life of the stream
        conn = await asyncpg.connect(LISTEN_DSN, timeout=DB_TIMEOUT_SECONDS,
                                     command_timeout=DB_TIMEOUT_SECONDS)
        conn.add_termination_listener(lambda _: queue.put_nowait(None))
        await conn.add_listener(NOTIFY_CHANNEL, on_notify)
    except Exception:
        logger.exception("Could not start the event stream listener")
        if conn:
            conn.terminate()
        raise HTTPException(status_code=503, detail="Event stream unavailable")
    return _ListenerStreamingResponse(
        _sse_messages(queue), conn, on_notify,
        media_type="text/event-stream",
        # no-transform stops proxies (including Next.js compression) from buffering
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )

@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(data: EventCreate, db: AsyncSession = Depends(get_db)):
    if data.project_id:
        proj = await db.execute(select(Project.id).where(Project.id == data.project_id))
        if not proj.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")
    event = await emit(**data.model_dump())
    if not event:
        raise HTTPException(status_code=503, detail="Event could not be stored")
    return event
