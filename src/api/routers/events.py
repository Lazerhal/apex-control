from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Event, Project
from src.api.schemas import EventCreate, EventResponse
from src.events import emit
import uuid

router = APIRouter(prefix="/api/events", tags=["events"])

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
