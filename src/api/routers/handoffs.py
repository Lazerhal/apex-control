from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Handoff, DocSyncState
from src.api.dependencies import require_project
from src.api.schemas import HandoffCreate, HandoffResponse
from src.events import emit
from datetime import datetime, date, timezone
import uuid

router = APIRouter(prefix="/api/projects/{project_id}/handoffs", tags=["handoffs"])

@router.get("", response_model=list[HandoffResponse])
async def list_handoffs(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id)
    result = await db.execute(select(Handoff).where(Handoff.project_id == project_id).order_by(Handoff.created_at.desc()).limit(10))
    handoffs = result.scalars().all()
    for h in handoffs:
        h.session_date = str(h.session_date)
    return handoffs

@router.post("", response_model=HandoffResponse, status_code=status.HTTP_201_CREATED)
async def create_handoff(project_id: uuid.UUID, data: HandoffCreate, db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id, lock=True)
    handoff = Handoff(project_id=project_id, session_date=date.today(), **data.model_dump())
    db.add(handoff)
    sync = await db.execute(select(DocSyncState).where(DocSyncState.project_id == project_id))
    sync_state = sync.scalar_one_or_none()
    if sync_state:
        sync_state.last_db_write = datetime.now(timezone.utc)
        sync_state.sync_status = "db_ahead"
    await db.commit()
    await db.refresh(handoff)
    await emit("handoff.created", "api", project_id=project_id,
               payload={"handoff_id": str(handoff.id), "session_tool": handoff.session_tool})
    handoff.session_date = str(handoff.session_date)
    return handoff
