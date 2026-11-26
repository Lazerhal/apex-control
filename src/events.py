"""Event bus: record what happens across APEX in the events table."""
import asyncio
import logging
import uuid
from typing import Optional

from src.db.models import Event
from src.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Upper bound on how long a slow database can delay the caller.
EMIT_TIMEOUT_SECONDS = 5


async def _store(event: Event) -> None:
    async with AsyncSessionLocal() as session:
        session.add(event)
        await session.commit()


async def emit(
    kind: str,
    source: str,
    target: Optional[str] = None,
    project_id: Optional[uuid.UUID] = None,
    actor: Optional[str] = None,
    status: str = "ok",
    payload: Optional[dict] = None,
    latency_ms: Optional[int] = None,
    cost_usd: Optional[float] = None,
) -> Optional[Event]:
    """Store one event in its own session. Never raises.

    Returns the stored event, or None if it could not be stored.
    """
    try:
        event = Event(
            kind=kind,
            source=source,
            target=target,
            project_id=project_id,
            actor=actor,
            status=status,
            payload=payload or {},
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        )
        await asyncio.wait_for(_store(event), timeout=EMIT_TIMEOUT_SECONDS)
        return event
    except Exception:
        logger.exception("Failed to emit event kind=%s source=%s", kind, source)
        return None
