"""The guard that keeps tests away from live data."""
import os
import subprocess
import sys

import pytest

from tests.conftest import ROOT
from tests.db_guard import UnsafeDatabaseError, check_database_is_empty, check_database_url


@pytest.mark.parametrize("url", [
    "postgresql://u:p@127.0.0.1:5432/apex_test",
    "postgresql+asyncpg://u:p@localhost:61234/apex_test",
])
def test_accepts_local_test_database(url):
    assert check_database_url(url) == url


@pytest.mark.parametrize("url", [
    "postgresql://u:p@127.0.0.1:5433/apex_test",             # live port, even with a test name
    "postgresql://u:p@localhost:5433/apex",
    "postgresql://u:p@127.0.0.1:5432/apex",                  # live database name on another port
    "postgresql://u:p@127.0.0.1:5432/apex_control",
    "postgresql://u:p@127.0.0.1:5432/postgres",
    "postgresql://u:p@127.0.0.1/apex_test",                  # no port
    "postgresql://u:p@db.example.com:5432/apex_test",        # not local
    "postgresql://u:p@127.0.0.1:5432/apex_test?port=5433",   # override through the query
    "postgresql://u:p@127.0.0.1:5432/apex_test?host=elsewhere",
    "postgresql://u:p@127.0.0.1:5432,127.0.0.1:5433/apex_test",
    "sqlite:///apex_test",
    "",
])
def test_refuses_anything_else(url):
    with pytest.raises(UnsafeDatabaseError) as error:
        check_database_url(url)
    assert "u:p" not in str(error.value)


def test_refuses_database_with_tables():
    check_database_is_empty(0)
    with pytest.raises(UnsafeDatabaseError):
        check_database_is_empty(1)


@pytest.mark.parametrize("variable", ["DATABASE_URL", "TEST_DATABASE_URL"])
def test_pytest_stops_before_running_against_live(variable):
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "TEST_DATABASE_URL")}
    env[variable] = "postgresql://apex:secret@127.0.0.1:5433/apex"
    run = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_guard.py"],
                         cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    output = run.stdout + run.stderr
    assert run.returncode == 4, output
    assert "Refusing to run tests" in output and "secret" not in output
    assert "passed" not in output


def test_app_uses_the_test_database(database):
    from src.db.session import db_url
    assert db_url == database.replace("postgresql://", "postgresql+asyncpg://")
