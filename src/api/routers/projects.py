from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.db.session import get_db
from src.db.models import Project, DocSyncState
from src.api.schemas import ProjectCreate, ProjectUpdate, ProjectResponse, MessageResponse
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/projects", tags=["projects"])

def generate_apex_id(project_type: str) -> str:
    type_codes = {
        "product-tool": "PROD",
        "content-engine": "CONT",
        "saas": "SAAS",
        "governed-system": "GOV",
        "infrastructure": "INFRA",
        "idea": "IDEA",
    }
    code = type_codes.get(project_type, "PROJ")
    now = datetime.utcnow()
    seq = str(uuid.uuid4())[:4].upper()
    return f"APEX-{code}-{now.strftime('%Y%m')}-{seq}"

@router.get("", response_model=list[ProjectResponse])
async def list_projects(stage: str | None = None, type: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Project).where(Project.deleted_at.is_(None))
    if stage:
        query = query.where(Project.stage == stage)
    if type:
        query = query.where(Project.type == type)
    query = query.order_by(Project.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(apex_id=generate_apex_id(data.type), **data.model_dump())
    db.add(project)
    await db.flush()
    doc_sync = DocSyncState(project_id=project.id, sync_status="in_sync", last_db_write=datetime.utcnow())
    db.add(doc_sync)
    await db.commit()
    await db.refresh(project)
    return project

@router.get("/apex/{apex_id}", response_model=ProjectResponse)
async def get_project_by_apex_id(apex_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.apex_id == apex_id, Project.deleted_at.is_(None)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.deleted_at.is_(None)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: uuid.UUID, data: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.deleted_at.is_(None)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project

@router.delete("/{project_id}", response_model=MessageResponse)
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.deleted_at.is_(None)))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project.deleted_at = datetime.utcnow()
    await db.commit()
    return {"message": f"Project {project.name} deleted"}
