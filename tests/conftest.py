"""Test setup: a throwaway Postgres 16, migrated with `alembic upgrade head`.

By default a Docker container is started and removed again. Set TEST_DATABASE_URL to use an
empty database that already exists (CI uses a service container).
"""
import asyncio
import contextlib
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from tests.db_guard import UnsafeDatabaseError, check_database_is_empty, check_database_url

ROOT = Path(__file__).resolve().parent.parent
USERNAME, PASSWORD, BOT_TOKEN = "tester", "correct-test-password", "test-bot-token"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── Environment: must be settled before anything imports src ──────

try:
    # A URL already in the environment is checked even though DATABASE_URL gets replaced
    for _name in ("DATABASE_URL", "TEST_DATABASE_URL"):
        if os.environ.get(_name):
            check_database_url(os.environ[_name])
except UnsafeDatabaseError as e:
    pytest.exit(str(e), returncode=4)

EXTERNAL_URL = os.environ.get("TEST_DATABASE_URL")
CONTAINER_PORT = None if EXTERNAL_URL else _free_port()
DATABASE_URL = check_database_url(
    EXTERNAL_URL or f"postgresql://postgres:test@127.0.0.1:{CONTAINER_PORT}/apex_test"
)

from passlib.context import CryptContext  # noqa: E402
from src.config import Settings  # noqa: E402

# Never read .env: not the app's settings, and not Alembic's load_dotenv()
Settings.model_config["env_file"] = None
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for _key in list(os.environ):
    # Drop real settings and libpq overrides inherited from the shell
    if _key.lower() in Settings.model_fields or _key.startswith("PG"):
        del os.environ[_key]
os.environ.update(
    DATABASE_URL=DATABASE_URL,
    APEX_SESSION_SECRET="test-session-secret",
    JWT_SECRET_KEY="test-jwt-secret",
    APEX_DASHBOARD_USERNAME=USERNAME,
    APEX_DASHBOARD_PASSWORD_HASH=CryptContext(schemes=["bcrypt"]).hash(PASSWORD),
    TELEGRAM_BOT_TOKEN=BOT_TOKEN,
    TELEGRAM_OWNER_CHAT_ID="1",
    DEBUG="false",
    ENVIRONMENT="test",
)

import asyncpg  # noqa: E402
import httpx  # noqa: E402
import psycopg2  # noqa: E402
import uvicorn  # noqa: E402


# ── Database ──────────────────────────────────────────────────────

def _connect_when_ready(timeout: float = 60):
    deadline = time.monotonic() + timeout
    while True:
        try:
            return psycopg2.connect(DATABASE_URL, connect_timeout=3)
        except psycopg2.OperationalError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)


def alembic(*args: str, url: str = DATABASE_URL) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args], cwd=ROOT, capture_output=True, text=True,
        env={**os.environ, "DATABASE_URL": url},
    )


@pytest.fixture(scope="session", autouse=True)
def database():
    container = None
    if not EXTERNAL_URL:
        container = f"apex-test-pg-{uuid.uuid4().hex[:8]}"
        subprocess.run(
            ["docker", "run", "-d", "--rm", "--name", container,
             "-e", "POSTGRES_PASSWORD=test", "-e", "POSTGRES_DB=apex_test",
             "-p", f"127.0.0.1:{CONTAINER_PORT}:5432", "postgres:16-alpine"],
            check=True, capture_output=True, text=True,
        )
    try:
        with contextlib.closing(_connect_when_ready()) as conn, conn.cursor() as cur:
            cur.execute("select count(*) from pg_tables "
                        "where schemaname not in ('pg_catalog', 'information_schema')")
            try:
                check_database_is_empty(cur.fetchone()[0])
            except UnsafeDatabaseError as e:
                pytest.exit(str(e), returncode=4)
            assert conn.server_version // 10000 == 16, "tests expect Postgres 16"
        result = alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr
        yield DATABASE_URL
    finally:
        if container:
            subprocess.run(["docker", "rm", "-f", container], capture_output=True)


@pytest.fixture
async def db(database):
    conn = await asyncpg.connect(database)
    yield conn
    await conn.close()


@pytest.fixture(autouse=True)
async def clean_tables(db):
    from src.db.base import Base
    import src.db.models  # noqa: F401
    tables = ", ".join(f'"{name}"' for name in Base.metadata.tables)
    await db.execute(f"truncate {tables} cascade")


@pytest.fixture(scope="session", autouse=True)
async def dispose_engine(database):
    yield
    from src.db.session import engine
    await engine.dispose()


# ── API clients ───────────────────────────────────────────────────

@pytest.fixture
def app():
    from src.main import app
    return app


@pytest.fixture
async def anon(app):
    """Client without credentials. Unhandled errors come back as 500, as in production."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
        yield client


@pytest.fixture
def token():
    from src.auth import create_access_token
    return create_access_token({"sub": USERNAME, "type": "dashboard"})


@pytest.fixture
async def client(app, token):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="https://test",
                                 headers={"Authorization": f"Bearer {token}"}) as client:
        yield client


@pytest.fixture
async def project(client):
    res = await client.post("/api/projects", json={"name": "demo", "type": "saas"})
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture
def events_unavailable(db):
    """Context manager that makes every event write and read fail."""
    @contextlib.asynccontextmanager
    async def broken():
        await db.execute("alter table events rename to events_hidden")
        try:
            yield
        finally:
            await db.execute("alter table events_hidden rename to events")
    return broken


# ── A real server, for streams ────────────────────────────────────

class _Server(uvicorn.Server):
    @contextlib.contextmanager
    def capture_signals(self):
        yield  # leave Ctrl+C to pytest


@pytest.fixture
async def server(app):
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_config=None,
                            lifespan="off", timeout_graceful_shutdown=2)
    instance = _Server(config)
    task = asyncio.create_task(instance.serve())
    while not instance.started:
        assert not task.done(), "test server failed to start"
        await asyncio.sleep(0.01)
    port = instance.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    instance.should_exit = True
    await task
