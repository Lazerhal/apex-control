from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.config import get_settings
from src.api.routers import projects, tasks, notes, handoffs, ideas, dashboard

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
    allow_origins=["http://localhost:3000", "https://apex.lazerhal.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(notes.router)
app.include_router(handoffs.router)
app.include_router(ideas.router)
app.include_router(dashboard.router)

@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}

@app.get("/api")
async def root():
    return {"message": "APEX Control API", "version": "0.1.0"}
