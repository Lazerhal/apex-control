from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.db.session import get_db
from src.db.models import Project, Task, Idea, Recommendation

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    proj_result = await db.execute(select(Project.stage, func.count(Project.id)).where(Project.deleted_at.is_(None)).group_by(Project.stage))
    projects_by_stage = {row[0]: row[1] for row in proj_result}
    total_proj = await db.execute(select(func.count(Project.id)).where(Project.deleted_at.is_(None)))
    live_tasks = select(func.count(Task.id)).join(Project, Task.project_id == Project.id).where(
        Project.deleted_at.is_(None), Task.status == "open")
    open_tasks = await db.execute(live_tasks)
    critical_tasks = await db.execute(live_tasks.where(Task.priority == "critical"))
    new_ideas = await db.execute(select(func.count(Idea.id)).where(Idea.status == "new", Idea.deleted_at.is_(None)))
    new_recs = await db.execute(
        select(func.count(Recommendation.id)).join(Project, Recommendation.project_id == Project.id)
        .where(Project.deleted_at.is_(None), Recommendation.status == "new"))
    total_cost = await db.execute(select(func.sum(Project.monthly_cost_usd)).where(Project.deleted_at.is_(None)))
    total_revenue = await db.execute(select(func.sum(Project.monthly_revenue_usd)).where(Project.deleted_at.is_(None)))
    cost = float(total_cost.scalar() or 0)
    revenue = float(total_revenue.scalar() or 0)
    return {
        "projects": {"total": total_proj.scalar() or 0, "by_stage": projects_by_stage},
        "tasks": {"open": open_tasks.scalar() or 0, "critical": critical_tasks.scalar() or 0},
        "ideas": {"new": new_ideas.scalar() or 0},
        "recommendations": {"new": new_recs.scalar() or 0},
        "financials": {
            "monthly_cost_usd": cost,
            "monthly_revenue_usd": revenue,
            "monthly_profit_usd": revenue - cost,
        }
    }
