from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.config import get_settings
from src.api.routers import projects, tasks, notes, handoffs, ideas, dashboard
from src.api.routers import auth as auth_router
from src.auth import get_current_user, get_current_user_or_bot

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"APEX Control starting — environment: {settings.environment}")
    yield
    print("APEX Control shutting down")

app = FastAPI(
    title="APEX Control API",
    description="Autonomous Project Execution and Control — backend API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://apex.lazerhal.dev", "https://api.lazerhal.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes
app.include_router(auth_router.router)

# Protected routes — require valid session token
app.include_router(projects.router, dependencies=[Depends(get_current_user_or_bot)])
app.include_router(tasks.router, dependencies=[Depends(get_current_user_or_bot)])
app.include_router(notes.router, dependencies=[Depends(get_current_user_or_bot)])
app.include_router(handoffs.router, dependencies=[Depends(get_current_user_or_bot)])
app.include_router(ideas.router, dependencies=[Depends(get_current_user_or_bot)])
app.include_router(dashboard.router, dependencies=[Depends(get_current_user_or_bot)])

@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}

@app.get("/api")
async def root():
    return {"message": "APEX Control API", "version": "0.1.0"}
