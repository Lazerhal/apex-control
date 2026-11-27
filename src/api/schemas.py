from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional
from datetime import datetime
import math
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
    monthly_cost_usd: float = Field(default=0, allow_inf_nan=False)
    monthly_revenue_usd: float = Field(default=0, allow_inf_nan=False)

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    stage: Optional[str] = None
    short_description: Optional[str] = None
    goal: Optional[str] = None
    status_note: Optional[str] = None
    live_url: Optional[str] = None
    github_repo: Optional[str] = None
    monthly_cost_usd: Optional[float] = Field(default=None, allow_inf_nan=False)
    monthly_revenue_usd: Optional[float] = Field(default=None, allow_inf_nan=False)
    cost_efficiency_flag: Optional[str] = None

    @field_validator("monthly_cost_usd", "monthly_revenue_usd", "cost_efficiency_flag")
    @classmethod
    def not_null(cls, value):
        # Runs only for fields that were sent: leaving one out is fine, null is not
        if value is None:
            raise ValueError("cannot be null")
        return value

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

    # Rows saved before nulls were rejected must not break reading projects
    @field_validator("monthly_cost_usd", "monthly_revenue_usd", mode="before")
    @classmethod
    def missing_amount_is_zero(cls, value):
        return 0 if value is None or not math.isfinite(value) else value

    @field_validator("cost_efficiency_flag", mode="before")
    @classmethod
    def missing_flag_is_healthy(cls, value):
        return "healthy" if value is None else value

    @field_validator("completeness_score", mode="before")
    @classmethod
    def missing_score_is_zero(cls, value):
        return 0 if value is None else value

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    type: str = "feature"
    estimated_effort: Optional[str] = None
    assigned_to: Optional[str] = None

class TaskUpdate(BaseModel):
    """The only task fields a client may change. Anything else is rejected."""
    model_config = ConfigDict(extra="forbid")

    # A None default with a non-Optional type: may be left out, but not set to null
    title: str = Field(default=None, max_length=300)
    description: Optional[str] = None
    priority: str = Field(default=None, max_length=20)
    type: str = Field(default=None, max_length=30)
    estimated_effort: Optional[str] = Field(default=None, max_length=20)
    assigned_to: Optional[str] = Field(default=None, max_length=100)
    blocked_by: Optional[list[str]] = None
    status: str = Field(default=None, max_length=20)

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

class EventCreate(BaseModel):
    kind: str = Field(min_length=1, max_length=50)
    source: str = Field(min_length=1, max_length=30)
    target: Optional[str] = Field(default=None, max_length=50)
    project_id: Optional[uuid.UUID] = None
    actor: Optional[str] = Field(default=None, max_length=50)
    status: str = Field(default="ok", min_length=1, max_length=20)
    payload: dict = Field(default_factory=dict)
    latency_ms: Optional[int] = Field(default=None, ge=0, le=2_147_483_647)
    cost_usd: Optional[float] = Field(default=None, ge=0, lt=10_000)

class EventResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    kind: str
    source: str
    target: Optional[str]
    project_id: Optional[uuid.UUID]
    actor: Optional[str]
    status: str
    latency_ms: Optional[int]
    cost_usd: Optional[float]
    payload: dict
    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    message: str
