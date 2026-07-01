from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Idea
from src.api.schemas import IdeaCreate, IdeaResponse
import uuid

router = APIRouter(prefix="/api/ideas", tags=["ideas"])

@router.get("", response_model=list[IdeaResponse])
async def list_ideas(status: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Idea).where(Idea.deleted_at.is_(None))
    if status:
        query = query.where(Idea.status == status)
    result = await db.execute(query.order_by(Idea.created_at.desc()))
    return result.scalars().all()

@router.post("", response_model=IdeaResponse, status_code=status.HTTP_201_CREATED)
async def create_idea(data: IdeaCreate, db: AsyncSession = Depends(get_db)):
    idea = Idea(**data.model_dump())
    db.add(idea)
    await db.commit()
    await db.refresh(idea)
    return idea

@router.get("/{idea_id}", response_model=IdeaResponse)
async def get_idea(idea_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Idea).where(Idea.id == idea_id, Idea.deleted_at.is_(None)))
    idea = result.scalar_one_or_none()
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea
