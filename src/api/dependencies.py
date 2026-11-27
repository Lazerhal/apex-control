import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Project


async def require_project(db: AsyncSession, project_id: uuid.UUID, lock: bool = False) -> None:
    """404 unless the project exists and is not deleted.

    Writes pass lock=True: the project row stays locked until commit, so the project cannot be
    deleted in between, and writes to one project take turns.
    """
    query = select(Project.id).where(Project.id == project_id, Project.deleted_at.is_(None))
    if lock:
        query = query.with_for_update(key_share=True)
    if (await db.execute(query)).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Project not found")
