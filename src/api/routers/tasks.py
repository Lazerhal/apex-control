from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Task, Project
from src.api.schemas import TaskCreate, TaskResponse, MessageResponse
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/projects/{project_id}/tasks", tags=["tasks"])

@router.get("", response_model=list[TaskResponse])
async def list_tasks(project_id: uuid.UUID, status: str | None = None, priority: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Task).where(Task.project_id == project_id)
    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
    result = await db.execute(query.order_by(Task.created_at.desc()))
    return result.scalars().all()

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(project_id: uuid.UUID, data: TaskCreate, db: AsyncSession = Depends(get_db)):
    proj = await db.execute(select(Project).where(Project.id == project_id, Project.deleted_at.is_(None)))
    if not proj.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")
    count_result = await db.execute(select(Task).where(Task.project_id == project_id))
    count = len(count_result.scalars().all())
    task = Task(project_id=project_id, apex_task_id=f"T-{str(count+1).zfill(3)}", **data.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task

@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(project_id: uuid.UUID, task_id: uuid.UUID, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).where(Task.id == task_id, Task.project_id == project_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in data.items():
        if hasattr(task, field):
            setattr(task, field, value)
    if data.get("status") == "done":
        task.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    return task
