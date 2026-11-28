from fastapi import FastAPI, Depends, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import math
from src.config import get_settings
from src.api.routers import projects, tasks, notes, handoffs, ideas, dashboard, events
from src.api.routers import auth as auth_router
from src.auth import get_current_user, get_current_user_or_bot

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"APEX Control starting — environment: {settings.environment}")
    if not settings.apex_internal_key:
        print("APEX_INTERNAL_KEY is not set: bot authentication is disabled")
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

# Deeper input is cut off in 422 replies: writing it out would exceed the recursion limit
MAX_REPLY_DEPTH = 32

def _json_safe(value, depth=0):
    if depth > MAX_REPLY_DEPTH:
        return "..."
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, str):  # lone surrogates cannot be encoded
        return value.encode("utf-8", "replace").decode("utf-8")
    if isinstance(value, bytes):  # a body that was not sent as JSON
        return value.decode("utf-8", "replace")
    if isinstance(value, dict):
        return {_json_safe(k, depth + 1): _json_safe(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v, depth + 1) for v in value]
    return value

@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # The 422 reply repeats the input, and some input cannot be written as JSON (a 500)
    return await request_validation_exception_handler(
        request, RequestValidationError(_json_safe(exc.errors())))

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
app.include_router(events.router, dependencies=[Depends(get_current_user_or_bot)])

@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}

@app.get("/api")
async def root():
    return {"message": "APEX Control API", "version": "0.1.0"}
