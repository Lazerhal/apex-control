from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Note, Project
from src.api.schemas import NoteCreate, NoteResponse
import uuid

router = APIRouter(prefix="/api/projects/{project_id}/notes", tags=["notes"])

@router.get("", response_model=list[NoteResponse])
async def list_notes(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Note).where(Note.project_id == project_id).order_by(Note.created_at.desc()))
    return result.scalars().all()

@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(project_id: uuid.UUID, data: NoteCreate, db: AsyncSession = Depends(get_db)):
    proj = await db.execute(select(Project).where(Project.id == project_id, Project.deleted_at.is_(None)))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")
    note = Note(project_id=project_id, **data.model_dump())
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note
