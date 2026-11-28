"""Startup refuses weak secrets, without printing them."""
import os
import subprocess
import sys

import pytest

from tests.conftest import JWT_SECRET, ROOT


def start(tmp_path, module="src.main", **env):
    """Imports a module in a new process, away from any .env file. None removes a variable."""
    environment = {**os.environ, "PYTHONPATH": str(ROOT), **env}
    environment = {k: v for k, v in environment.items() if v is not None}
    return subprocess.run([sys.executable, "-c", f"import {module}"], cwd=tmp_path, env=environment,
                          capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("secret", [None, "", "short-secret-value", "x" * 31, " " * 40])
@pytest.mark.parametrize("module", ["src.main", "src.telegram_bot.bot"])
def test_weak_jwt_secret_stops_startup(tmp_path, secret, module):
    run = start(tmp_path, module, JWT_SECRET_KEY=secret)
    assert run.returncode != 0
    assert "JWT_SECRET_KEY must be set to at least 32 characters" in run.stderr


@pytest.mark.parametrize("secret", ["x" * 32, JWT_SECRET])
def test_long_enough_jwt_secret_starts(tmp_path, secret):
    run = start(tmp_path, JWT_SECRET_KEY=secret)
    assert run.returncode == 0, run.stderr


@pytest.mark.parametrize("variable", ["JWT_SECRET_KEY", "APEX_INTERNAL_KEY"])
def test_startup_errors_do_not_print_secrets(tmp_path, variable):
    run = start(tmp_path, **{variable: "visible-if-leaked"})
    assert run.returncode != 0 and variable in run.stderr
    output = run.stdout + run.stderr
    for secret in ("visible-if-leaked", os.environ["APEX_SESSION_SECRET"], os.environ["DATABASE_URL"],
                   os.environ["APEX_DASHBOARD_PASSWORD_HASH"]):
        assert secret not in output


def test_missing_setting_error_does_not_print_the_others(tmp_path):
    run = start(tmp_path, DATABASE_URL=None)
    assert run.returncode != 0 and "database_url" in run.stderr
    assert JWT_SECRET not in run.stdout + run.stderr


@pytest.mark.parametrize("key", [None, "", "k" * 32])
def test_internal_key_may_be_absent_or_long(tmp_path, key):
    run = start(tmp_path, APEX_INTERNAL_KEY=key)
    assert run.returncode == 0, run.stderr


def test_short_internal_key_stops_startup(tmp_path):
    run = start(tmp_path, APEX_INTERNAL_KEY="k" * 31)
    assert run.returncode != 0 and "APEX_INTERNAL_KEY must be at least 32" in run.stderr


@pytest.mark.parametrize("module", ["src.main", "src.telegram_bot.bot"])
@pytest.mark.parametrize("key", ["\u00e9" * 32, "k" * 40 + "\u2019"])
def test_non_ascii_internal_key_stops_startup(tmp_path, module, key):
    run = start(tmp_path, module, APEX_INTERNAL_KEY=key)
    assert run.returncode != 0
    assert "APEX_INTERNAL_KEY must contain only ASCII characters" in run.stderr
    assert key not in run.stdout + run.stderr
