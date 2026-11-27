from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.session import get_db
from src.db.models import Task
from src.api.dependencies import require_project
from src.api.schemas import SafeText, TaskCreate, TaskUpdate, TaskResponse
from src.events import emit
from datetime import datetime, timezone
import re
import uuid

router = APIRouter(prefix="/api/projects/{project_id}/tasks", tags=["tasks"])

@router.get("", response_model=list[TaskResponse])
async def list_tasks(project_id: uuid.UUID, status: SafeText | None = None, priority: SafeText | None = None, db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id)
    query = select(Task).where(Task.project_id == project_id)
    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
    result = await db.execute(query.order_by(Task.created_at.desc()))
    return result.scalars().all()

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(project_id: uuid.UUID, data: TaskCreate, db: AsyncSession = Depends(get_db)):
    # The lock makes creates in one project take turns, so two of them cannot pick the same
    # task number
    await require_project(db, project_id, lock=True)
    existing = await db.execute(select(Task.apex_task_id).where(Task.project_id == project_id))
    numbers = [int(m.group(1)) for i in existing.scalars() if (m := re.fullmatch(r"T-(\d+)", i or ""))]
    task = Task(project_id=project_id, apex_task_id=f"T-{max(numbers, default=0) + 1:03d}",
                **data.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await emit("task.created", "api", project_id=project_id,
               payload={"task_id": str(task.id), "apex_task_id": task.apex_task_id, "title": task.title})
    return task

@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(project_id: uuid.UUID, task_id: uuid.UUID, data: TaskUpdate, db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id, lock=True)
    result = await db.execute(select(Task).where(Task.id == task_id, Task.project_id == project_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(task, field, value)
    if "status" in changes:
        task.completed_at = datetime.now(timezone.utc) if changes["status"] == "done" else None
    await db.commit()
    await db.refresh(task)
    await emit("task.updated", "api", project_id=project_id,
               payload={"task_id": str(task.id), "apex_task_id": task.apex_task_id,
                        "fields": sorted(changes),
                        "task_status": task.status})
    return task
