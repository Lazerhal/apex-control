import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Numeric,
    DateTime, Date, ForeignKey, ARRAY, Enum as SAEnum,
    UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from src.db.base import Base


# ── Enums ─────────────────────────────────────────────────────────

class ProjectType(str, enum.Enum):
    product_tool = "product-tool"
    content_engine = "content-engine"
    saas = "saas"
    governed_system = "governed-system"
    infrastructure = "infrastructure"
    idea = "idea"

class ProjectStage(str, enum.Enum):
    idea = "idea"
    planning = "planning"
    active_development = "active-development"
    live = "live"
    paused = "paused"
    retired = "retired"

class TaskPriority(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    backlog = "backlog"

class TaskType(str, enum.Enum):
    bug = "bug"
    feature = "feature"
    improvement = "improvement"
    infrastructure = "infrastructure"
    documentation = "documentation"
    research = "research"
    security = "security"

class IssueSeverity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"

class IssueType(str, enum.Enum):
    bug = "bug"
    security = "security"
    performance = "performance"
    ux = "ux"
    debt = "debt"
    missing_feature = "missing-feature"


# ── Core Tables ───────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    apex_id = Column(String(30), unique=True, nullable=False)
    name = Column(String(60), nullable=False)
    type = Column(String(20), nullable=False)
    stage = Column(String(30), nullable=False, default="planning")
    owner = Column(String(100), nullable=False, default="Hunter Lazenby")
    short_description = Column(Text)
    goal = Column(Text)
    status_note = Column(Text)
    live_url = Column(String(500))
    internal_url = Column(String(500))
    github_repo = Column(String(500))
    repo_visibility = Column(String(10))
    primary_branch = Column(String(50), default="main")
    local_path = Column(String(500))
    monthly_cost_usd = Column(Numeric(10, 2), default=0)
    monthly_revenue_usd = Column(Numeric(10, 2), default=0)
    cost_efficiency_flag = Column(String(20), default="healthy")
    completeness_score = Column(Integer, default=0)
    metadata_ = Column("metadata", JSONB, default=dict)
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="project", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="project", cascade="all, delete-orphan")
    known_issues = relationship("KnownIssue", back_populates="project", cascade="all, delete-orphan")
    risks = relationship("Risk", back_populates="project", cascade="all, delete-orphan")
    cost_items = relationship("CostItem", back_populates="project", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="project", cascade="all, delete-orphan")
    env_vars = relationship("EnvVarRequirement", back_populates="project", cascade="all, delete-orphan")
    metric_snapshots = relationship("MetricSnapshot", back_populates="project", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="project", cascade="all, delete-orphan")
    handoffs = relationship("Handoff", back_populates="project", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="project", cascade="all, delete-orphan")
    doc_sync_state = relationship("DocSyncState", back_populates="project", uselist=False, cascade="all, delete-orphan")
    approval_requests = relationship("ApprovalRequest", back_populates="project", cascade="all, delete-orphan")


class Idea(Base):
    __tablename__ = "ideas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(120), nullable=False)
    raw_description = Column(Text, nullable=False)
    structured_description = Column(Text)
    clarification_state = Column(JSONB, default=dict)
    score_total = Column(Integer)
    score_breakdown = Column(JSONB)
    score_explanation = Column(Text)
    recommendation = Column(String(30))
    promoted_to_project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    status = Column(String(20), default="new")
    source = Column(String(50), default="telegram")
    deleted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    parent_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"))
    apex_task_id = Column(String(10))
    title = Column(String(300), nullable=False)
    description = Column(Text)
    priority = Column(String(20), nullable=False, default="medium")
    type = Column(String(30), nullable=False, default="feature")
    estimated_effort = Column(String(20))
    assigned_to = Column(String(100))
    blocked_by = Column(ARRAY(Text))
    status = Column(String(20), default="open")
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="tasks")
    # subtasks relationship defined in migration v2 to avoid self-referential complexity


class Note(Base):
    __tablename__ = "notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(50), default="dashboard")
    tags = Column(ARRAY(Text), default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="notes")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    apex_decision_id = Column(String(10))
    date = Column(Date, nullable=False, server_default=func.current_date())
    title = Column(String(200), nullable=False)
    context = Column(Text, nullable=False)
    options_considered = Column(ARRAY(Text))
    decision_made = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    made_by = Column(String(100), default="Hunter Lazenby")
    revisit_trigger = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="decisions")


class KnownIssue(Base):
    __tablename__ = "known_issues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    apex_issue_id = Column(String(10))
    description = Column(Text, nullable=False)
    severity = Column(String(10), nullable=False)
    type = Column(String(30), nullable=False)
    discovered_date = Column(Date)
    workaround = Column(Text)
    fix_status = Column(String(20), default="open")
    resolved_at = Column(DateTime(timezone=True))
    linked_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="known_issues")


class Risk(Base):
    __tablename__ = "risks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    apex_risk_id = Column(String(10))
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    likelihood = Column(String(10), nullable=False)
    impact = Column(String(10), nullable=False)
    mitigation = Column(Text, nullable=False)
    status = Column(String(20), default="open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="risks")


class CostItem(Base):
    __tablename__ = "cost_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)
    amount_usd = Column(Numeric(10, 4), nullable=False, default=0)
    billing_date = Column(String(50))
    notes = Column(Text)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="cost_items")


class Service(Base):
    __tablename__ = "services"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    purpose = Column(Text, nullable=False)
    tier = Column(String(50))
    monthly_cost_usd = Column(Numeric(10, 2), default=0)
    dashboard_url = Column(String(500))
    criticality = Column(String(20), nullable=False, default="important")
    status = Column(String(20), default="active")
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="services")


class EnvVarRequirement(Base):
    __tablename__ = "env_var_requirements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    var_name = Column(String(100), nullable=False)
    purpose = Column(Text, nullable=False)
    required = Column(Boolean, default=True)
    stored_in = Column(String(200))
    sensitive = Column(Boolean, default=True)
    present = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="env_vars")


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    value = Column(Numeric(14, 4))
    value_text = Column(String(200))
    unit = Column(String(30))
    source = Column(String(50), nullable=False)
    period_start = Column(Date)
    period_end = Column(Date)
    snapshot_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="metric_snapshots")

    __table_args__ = (
        Index("idx_metric_snapshots_project_metric",
              "project_id", "metric_name", "snapshot_at"),
    )


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    type = Column(String(30), nullable=False)
    severity = Column(String(10), nullable=False)
    title = Column(String(200), nullable=False)
    rationale = Column(Text, nullable=False)
    supporting_signals = Column(ARRAY(Text))
    estimated_effort = Column(String(10))
    expected_benefit = Column(Text)
    suggested_action = Column(Text)
    status = Column(String(20), default="new")
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="recommendations")


class Handoff(Base):
    __tablename__ = "handoffs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    session_date = Column(Date, nullable=False, server_default=func.current_date())
    session_tool = Column(String(100))
    what_was_done = Column(Text, nullable=False)
    what_remains = Column(Text, nullable=False)
    what_is_blocked = Column(Text, nullable=False, default="Nothing")
    next_model_should = Column(Text, nullable=False)
    context_pack_id = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="handoffs")


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    apex_exp_id = Column(String(10))
    title = Column(String(200), nullable=False)
    hypothesis = Column(Text, nullable=False)
    method = Column(Text, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    result = Column(Text)
    conclusion = Column(String(20))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="experiments")


class DocSyncState(Base):
    __tablename__ = "doc_sync_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    sync_status = Column(String(20), nullable=False, default="in_sync")
    last_db_write = Column(DateTime(timezone=True))
    last_markdown_write = Column(DateTime(timezone=True))
    last_sync_check = Column(DateTime(timezone=True))
    last_github_commit = Column(DateTime(timezone=True))
    freshness_warning = Column(Boolean, default=False)
    conflict_details = Column(Text)
    schema_version = Column(String(10), default="1.0")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="doc_sync_state")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    type = Column(String(50), nullable=False)
    risk_level = Column(String(10), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    proposed_action = Column(JSONB, nullable=False)
    requested_by = Column(String(100), nullable=False)
    status = Column(String(20), default="pending")
    expires_at = Column(DateTime(timezone=True))
    telegram_message_id = Column(String(100))
    responded_at = Column(DateTime(timezone=True))
    response_note = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="approval_requests")


class MachineState(Base):
    __tablename__ = "machine_state"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mode = Column(String(20), nullable=False, default="normal")
    fan_profile = Column(String(50))
    rgb_state = Column(String(20), default="on")
    display_state = Column(String(20), default="on")
    jobs_paused = Column(Boolean, default=False)
    ups_on_battery = Column(Boolean, default=False)
    ups_battery_pct = Column(Integer)
    ups_runtime_minutes = Column(Integer)
    notes = Column(Text)
    set_at = Column(DateTime(timezone=True), server_default=func.now())
    set_by = Column(String(50), default="manual")


class MachineStateHistory(Base):
    __tablename__ = "machine_state_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    previous_mode = Column(String(20))
    new_mode = Column(String(20))
    changed_by = Column(String(50))
    reason = Column(Text)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())


class PowerEvent(Base):
    __tablename__ = "power_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(30), nullable=False)
    ups_battery_pct_at_event = Column(Integer)
    ups_runtime_minutes_at_event = Column(Integer)
    action_taken = Column(Text)
    telegram_notified = Column(Boolean, default=False)
    jobs_paused = Column(Boolean, default=False)
    shutdown_initiated = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelRun(Base):
    __tablename__ = "model_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    task_type = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)
    routing_class = Column(String(10), nullable=False)
    prompt_package_id = Column(String(100))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    cost_usd = Column(Numeric(10, 6))
    data_sensitivity = Column(String(10), default="low")
    quality_score = Column(Integer)
    fallback_occurred = Column(Boolean, default=False)
    fallback_reason = Column(String(200))
    duration_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_model_runs_project_provider", "project_id", "provider", "created_at"),
    )


class ReusableAsset(Base):
    __tablename__ = "reusable_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    type = Column(String(30), nullable=False)
    description = Column(Text, nullable=False)
    source_project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    repo_path = Column(String(500))
    used_by_projects = Column(ARRAY(UUID(as_uuid=True)))
    tags = Column(ARRAY(Text), default=list)
    quality_score = Column(Integer)
    last_validated = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class JobsRegistry(Base):
    __tablename__ = "jobs_registry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    apscheduler_id = Column(String(100), unique=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    schedule = Column(String(100))
    last_run = Column(DateTime(timezone=True))
    last_result = Column(String(20))
    last_error = Column(Text)
    run_in_mode = Column(ARRAY(Text))
    overnight_safe = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── Project Type Extensions ───────────────────────────────────────

class ProjectExtProductTool(Base):
    __tablename__ = "project_ext_product_tool"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    maturity_level = Column(String(20), default="prototype")
    monetisation_options = Column(ARRAY(Text))
    distribution_channels = Column(ARRAY(Text))
    premium_upgrade_roadmap = Column(Text)
    marketplace_listings = Column(JSONB, default=list)


class ProjectExtContentEngine(Base):
    __tablename__ = "project_ext_content_engine"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    publishing_cadence = Column(String(100))
    content_pipeline = Column(Text)
    content_runway = Column(String(200))
    seo_status = Column(Text)
    analytics_status = Column(Text)
    scheduler_health = Column(String(20), default="unknown")
    monetisation_sources = Column(JSONB, default=list)
    promotion_channels = Column(ARRAY(Text))
    image_sources = Column(ARRAY(Text))


class ProjectExtSaas(Base):
    __tablename__ = "project_ext_saas"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    auth_flow = Column(Text)
    billing_flow = Column(Text)
    pricing_model = Column(JSONB, default=list)
    free_tier_limits = Column(Text)
    free_tier_enforcement = Column(String(20), default="client-side")
    conversion_funnel = Column(Text)
    churn_risks = Column(ARRAY(Text))
    growth_levers = Column(ARRAY(Text))
    affiliate_setup = Column(JSONB, default=list)
    mrr_usd = Column(Numeric(10, 2), default=0)
    active_subscribers = Column(Integer, default=0)


class ProjectExtGovernedSystem(Base):
    __tablename__ = "project_ext_governed_system"

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    current_stage = Column(String(30), default="stage-0-architecture")
    stage_gate_status = Column(JSONB, default=dict)
    governance_policy = Column(Text)
    approval_tree = Column(Text)
    risk_limits = Column(JSONB, default=list)
    champion_strategy = Column(Text)
    challenger_strategies = Column(ARRAY(Text))
    promotion_criteria = Column(Text)
    emergency_controls = Column(ARRAY(Text))
    safety_constraints = Column(ARRAY(Text))
    reference_frameworks = Column(ARRAY(Text))
