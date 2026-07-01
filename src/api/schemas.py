from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class ProjectCreate(BaseModel):
    name: str
    type: str
    stage: str = "planning"
    short_description: Optional[str] = None
    goal: Optional[str] = None
    status_note: Optional[str] = None
    live_url: Optional[str] = None
    github_repo: Optional[str] = None
    repo_visibility: Optional[str] = "private"
    primary_branch: str = "main"
    local_path: Optional[str] = None
    monthly_cost_usd: float = 0
    monthly_revenue_usd: float = 0

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    stage: Optional[str] = None
    short_description: Optional[str] = None
    goal: Optional[str] = None
    status_note: Optional[str] = None
    live_url: Optional[str] = None
    github_repo: Optional[str] = None
    monthly_cost_usd: Optional[float] = None
    monthly_revenue_usd: Optional[float] = None
    cost_efficiency_flag: Optional[str] = None

class ProjectResponse(BaseModel):
    id: uuid.UUID
    apex_id: str
    name: str
    type: str
    stage: str
    owner: str
    short_description: Optional[str]
    goal: Optional[str]
    status_note: Optional[str]
    live_url: Optional[str]
    github_repo: Optional[str]
    monthly_cost_usd: float
    monthly_revenue_usd: float
    cost_efficiency_flag: str
    completeness_score: int
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    type: str = "feature"
    estimated_effort: Optional[str] = None
    assigned_to: Optional[str] = None

class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    apex_task_id: Optional[str]
    title: str
    description: Optional[str]
    priority: str
    type: str
    estimated_effort: Optional[str]
    assigned_to: Optional[str]
    status: str
    created_at: datetime
    class Config:
        from_attributes = True

class NoteCreate(BaseModel):
    content: str
    source: str = "dashboard"
    tags: list[str] = []

class NoteResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    content: str
    source: str
    tags: list[str]
    created_at: datetime
    class Config:
        from_attributes = True

class HandoffCreate(BaseModel):
    session_tool: Optional[str] = None
    what_was_done: str
    what_remains: str
    what_is_blocked: str = "Nothing"
    next_model_should: str

class HandoffResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    session_date: str
    session_tool: Optional[str]
    what_was_done: str
    what_remains: str
    what_is_blocked: str
    next_model_should: str
    created_at: datetime
    class Config:
        from_attributes = True

class IdeaCreate(BaseModel):
    title: str
    raw_description: str
    source: str = "dashboard"

class IdeaResponse(BaseModel):
    id: uuid.UUID
    title: str
    raw_description: str
    score_total: Optional[int]
    recommendation: Optional[str]
    status: str
    source: str
    created_at: datetime
    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    message: str
