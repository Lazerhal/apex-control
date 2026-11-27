from tests.conftest import alembic


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
