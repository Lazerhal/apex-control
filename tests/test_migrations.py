from urllib.parse import quote, unquote, urlsplit, urlunsplit

import pytest

from tests.conftest import DATABASE_URL, alembic


async def test_upgrade_head_applied(db):
    assert await db.fetchval("select version_num from alembic_version") in alembic("heads").stdout


def test_single_head():
    assert len(alembic("heads").stdout.strip().splitlines()) == 1


async def test_events_trigger_and_indexes_exist(db):
    assert await db.fetchval("select count(*) from pg_trigger where tgname = 'events_notify_insert'") == 1
    indexes = {r[0] for r in await db.fetch("select indexname from pg_indexes where tablename = 'events'")}
    assert {"idx_events_created_at", "idx_events_project_created", "idx_events_kind"} <= indexes


async def test_downgrade_to_base_and_upgrade_again(db):
    down = alembic("downgrade", "base")
    try:
        assert down.returncode == 0, down.stderr
        assert await db.fetchval("select to_regclass('events')") is None
    finally:
        up = alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr
    from src.db.session import engine
    await engine.dispose()  # pooled connections must not reuse plans for dropped tables


def with_encoded_password(url: str) -> str:
    """The same URL with the password's first character percent-encoded, byte by byte."""
    parts = urlsplit(url)
    password = unquote(parts.password)
    first = "".join(f"%{byte:02X}" for byte in password[0].encode())
    encoded = first + quote(password[1:], safe="")
    userinfo, host = parts.netloc.rsplit("@", 1)
    result = urlunsplit(parts._replace(netloc=f"{userinfo.split(':', 1)[0]}:{encoded}@{host}"))
    assert encoded in result and unquote(urlsplit(result).password) == password
    return result


def test_migrations_accept_a_percent_encoded_password():
    result = alembic("current", url=with_encoded_password(DATABASE_URL))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("password,first", [
    ("secret", "%73"), ("\u00e9cret", "%C3%A9"), ("\u20ac%1", "%E2%82%AC"),
    ("\U0001f511k", "%F0%9F%94%91")])
def test_password_encoder_handles_any_first_character(password, first):
    url = f"postgresql://user:{quote(password, safe='')}@127.0.0.1:1/apex_test"
    assert f":{first}" in with_encoded_password(url)


async def test_migrations_accept_a_non_ascii_password(db):
    password = "\u00e9t\u00e9-%@:/\u20ac"
    await db.execute("drop role if exists apex_test_unicode")
    await db.execute(f"create role apex_test_unicode login superuser password '{password}'")
    try:
        parts = urlsplit(DATABASE_URL)
        netloc = f"apex_test_unicode:{quote(password, safe='')}@{parts.netloc.rsplit('@', 1)[1]}"
        result = alembic("current", url=urlunsplit(parts._replace(netloc=netloc)))
        assert result.returncode == 0, result.stderr
    finally:
        await db.execute("drop role apex_test_unicode")
