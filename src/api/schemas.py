from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator
from typing import Annotated, Optional
from datetime import datetime
from src.db.models import ProjectStage, ProjectType
import math
import uuid

# The largest amount a NUMERIC(10, 2) column holds
MAX_AMOUNT = 99_999_999.99
# Deeper event payloads cannot be written out again
MAX_PAYLOAD_DEPTH = 32


def _check_text(value):
    """Rejects text the database cannot store, also inside lists and objects."""
    pending = [value]  # a loop, not recursion: an event payload may be nested very deeply
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            if "\x00" in item:
                raise ValueError("cannot contain a null character")
            if any("\ud800" <= char <= "\udfff" for char in item):
                raise ValueError("must be valid Unicode text")
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return value


# For path and query parameters
SafeText = Annotated[str, AfterValidator(_check_text)]


class RequestModel(BaseModel):
    """Base for request bodies: no field may hold text the database cannot store."""

    @field_validator("*")
    @classmethod
    def storable_text(cls, value):
        return _check_text(value)


class ProjectCreate(RequestModel):
    model_config = ConfigDict(use_enum_values=True)

    name: str = Field(max_length=60)
    type: ProjectType
    stage: ProjectStage = "planning"
    short_description: Optional[str] = None
    goal: Optional[str] = None
    status_note: Optional[str] = None
    live_url: Optional[str] = Field(default=None, max_length=500)
    github_repo: Optional[str] = Field(default=None, max_length=500)
    repo_visibility: Optional[str] = Field(default="private", max_length=10)
    primary_branch: str = Field(default="main", max_length=50)
    local_path: Optional[str] = Field(default=None, max_length=500)
    monthly_cost_usd: float = Field(default=0, ge=-MAX_AMOUNT, le=MAX_AMOUNT, allow_inf_nan=False)
    monthly_revenue_usd: float = Field(default=0, ge=-MAX_AMOUNT, le=MAX_AMOUNT, allow_inf_nan=False)

class ProjectUpdate(RequestModel):
    model_config = ConfigDict(use_enum_values=True)

    name: Optional[str] = Field(default=None, max_length=60)
    stage: Optional[ProjectStage] = None
    short_description: Optional[str] = None
    goal: Optional[str] = None
    status_note: Optional[str] = None
    live_url: Optional[str] = Field(default=None, max_length=500)
    github_repo: Optional[str] = Field(default=None, max_length=500)
    monthly_cost_usd: Optional[float] = Field(
        default=None, ge=-MAX_AMOUNT, le=MAX_AMOUNT, allow_inf_nan=False)
    monthly_revenue_usd: Optional[float] = Field(
        default=None, ge=-MAX_AMOUNT, le=MAX_AMOUNT, allow_inf_nan=False)
    cost_efficiency_flag: Optional[str] = Field(default=None, max_length=20)

    @field_validator("name", "stage", "monthly_cost_usd", "monthly_revenue_usd",
                     "cost_efficiency_flag")
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

class TaskCreate(RequestModel):
    title: str = Field(max_length=300)
    description: Optional[str] = None
    priority: str = Field(default="medium", max_length=20)
    type: str = Field(default="feature", max_length=30)
    estimated_effort: Optional[str] = Field(default=None, max_length=20)
    assigned_to: Optional[str] = Field(default=None, max_length=100)

class TaskUpdate(RequestModel):
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

class NoteCreate(RequestModel):
    content: str
    source: str = Field(default="dashboard", max_length=50)
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

class HandoffCreate(RequestModel):
    session_tool: Optional[str] = Field(default=None, max_length=100)
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

class IdeaCreate(RequestModel):
    title: str = Field(max_length=120)
    raw_description: str
    source: str = Field(default="dashboard", max_length=50)

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

class EventCreate(RequestModel):
    kind: str = Field(min_length=1, max_length=50)
    source: str = Field(min_length=1, max_length=30)
    target: Optional[str] = Field(default=None, max_length=50)
    project_id: Optional[uuid.UUID] = None
    actor: Optional[str] = Field(default=None, max_length=50)
    status: str = Field(default="ok", min_length=1, max_length=20)
    payload: dict = Field(default_factory=dict)
    latency_ms: Optional[int] = Field(default=None, ge=0, le=2_147_483_647)
    cost_usd: Optional[float] = Field(default=None, ge=0, le=9_999.999999)  # NUMERIC(10, 6)

    @field_validator("payload")
    @classmethod
    def payload_can_be_stored(cls, value):
        pending = [(value, 1)]
        while pending:
            item, depth = pending.pop()
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("cannot contain NaN or Infinity")
            if isinstance(item, (dict, list)):
                if depth > MAX_PAYLOAD_DEPTH:
                    raise ValueError(f"cannot be nested more than {MAX_PAYLOAD_DEPTH} levels deep")
                children = item.values() if isinstance(item, dict) else item
                pending.extend((child, depth + 1) for child in children)
        return value

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
