"""Times set by Python are stored correctly whatever the server's timezone, and the SQL scripts
that check and correct older rows."""
import time

import pytest

from tests.conftest import ROOT

SQL = ROOT / "scripts" / "sql"


@pytest.fixture(params=["UTC", "America/Chicago", "Asia/Kolkata"])
def server_timezone(request, monkeypatch):
    monkeypatch.setenv("TZ", request.param)
    time.tzset()
    yield request.param
    monkeypatch.undo()
    time.tzset()


@pytest.mark.parametrize("column", ["projects.deleted_at", "doc_sync_states.last_db_write",
                                    "tasks.completed_at"])
async def test_stored_times_are_right(client, project, db, server_timezone, column):
    tasks = f"/api/projects/{project['id']}/tasks"
    task = (await client.post(tasks, json={"title": "t"})).json()
    await client.patch(f"{tasks}/{task['id']}", json={"status": "done"})
    await client.post(f"/api/projects/{project['id']}/handoffs", json={
        "what_was_done": "a", "what_remains": "b", "next_model_should": "c"})
    await client.delete(f"/api/projects/{project['id']}")
    table, name = column.split(".")
    drift = await db.fetchval(f"select abs(extract(epoch from now() - {name})) from {table}")
    assert drift < 60, f"{column} is off by {float(drift) / 3600:.1f} hours"


async def test_project_creation_time_is_right(client, db, server_timezone):
    await client.post("/api/projects", json={"name": "n", "type": "saas"})
    assert await db.fetchval(
        "select abs(extract(epoch from now() - last_db_write)) < 60 from doc_sync_states")


async def test_tokens_expire_when_expected(server_timezone):
    from jose import jwt
    from src.auth import create_access_token, settings
    claims = jwt.get_unverified_claims(create_access_token({"sub": "x"}))
    assert abs(claims["exp"] - time.time() - settings.jwt_expire_hours * 3600) < 60


# ── The SQL scripts ───────────────────────────────────────────────

def statements(name: str) -> list[str]:
    """The script's statements, without psql commands and transaction control."""
    lines = [line for line in (SQL / name).read_text().splitlines()
             if not line.lstrip().startswith(("\\", "--"))]
    parts = [part.strip() for part in "\n".join(lines).split(";")]
    return [p for p in parts if p and p.split()[0].upper() not in ("BEGIN", "COMMIT", "ROLLBACK")]


# (name, how far completed_at is from updated_at, verdict)
CASES = [
    ("correct", "0 seconds", None),
    ("shifted-summer", "5 hours", "shifted"),
    ("shifted-winter", "6 hours", "shifted"),
    ("shifted-then-edited", "2 hours", "shifted"),
    ("edited-later", "-3 days", "review"),
    ("far-ahead", "2 days", "review"),
]


async def seed(db, project):
    for name, difference, _ in CASES:
        updated = "2026-01-15 12:00+00" if name == "shifted-winter" else "2026-07-15 12:00+00"
        await db.execute(f"""
            insert into tasks (id, project_id, title, priority, type, status, updated_at, completed_at)
            values (gen_random_uuid(), $1::text::uuid, $2, 'medium', 'feature', 'done',
                    timestamptz '{updated}', timestamptz '{updated}' + interval '{difference}')
            """, project["id"], name)
    for table, column in (("projects", "deleted_at"), ("doc_sync_states", "last_db_write")):
        await db.execute(f"""update {table} set updated_at = timestamptz '2026-07-15 12:00+00',
                                            {column} = timestamptz '2026-07-15 17:00:00.2+00'""")


async def snapshot(db):
    return [tuple(r) for r in await db.fetch("""
        select title, completed_at - updated_at, updated_at from tasks
        union all select 'project', deleted_at - updated_at, updated_at from projects
        union all select 'sync', last_db_write - updated_at, updated_at from doc_sync_states
        order by 1""")]


async def test_check_script_reports_and_changes_nothing(client, project, db):
    await seed(db, project)
    before = await snapshot(db)
    async with db.transaction(readonly=True):
        results = [await db.fetch(s) for s in statements("check_naive_timestamps.sql")]
    assert await snapshot(db) == before
    titles = {r["id"]: r["title"] for r in await db.fetch("select id, title from tasks")}
    found = {titles[r["id"]]: r["verdict"] for r in results[1] if r["column_name"] == "tasks.completed_at"}
    assert found == {name: verdict for name, _, verdict in CASES if verdict}
    others = {(r["column_name"], r["verdict"]) for r in results[1]} - {
        ("tasks.completed_at", "shifted"), ("tasks.completed_at", "review")}
    assert others == {("projects.deleted_at", "shifted"), ("doc_sync_states.last_db_write", "shifted")}


def test_check_script_is_read_only():
    text = (SQL / "check_naive_timestamps.sql").read_text()
    assert "BEGIN TRANSACTION READ ONLY;" in text and text.rstrip().endswith("ROLLBACK;")


def test_fix_script_is_a_dry_run_unless_asked():
    text = (SQL / "fix_naive_timestamps.sql").read_text()
    tail = text[text.index("\\if :{?apply}"):]
    assert tail.index("COMMIT;") < tail.index("\\else") < tail.index("ROLLBACK;") < tail.index("\\endif")
    assert text.count("COMMIT;") == 1


async def test_fix_script_corrects_only_shifted_rows_and_only_once(client, project, db):
    await seed(db, project)
    before = {row[0]: row for row in await snapshot(db)}
    for _ in range(2):  # the second run must change nothing more
        async with db.transaction():
            for statement in statements("fix_naive_timestamps.sql"):
                await db.execute(statement)
        after = {row[0]: row for row in await snapshot(db)}
        hours = {name: row[1].total_seconds() / 3600 for name, row in after.items()}
        assert hours["shifted-summer"] == 0 and hours["shifted-winter"] == 0
        assert hours["shifted-then-edited"] == -3  # 2h shown, 5h offset: finished before the edit
        assert round(hours["project"], 2) == 0 and round(hours["sync"], 2) == 0
        for name in ("correct", "edited-later", "far-ahead"):
            assert after[name] == before[name]
        assert all(after[n][2] == before[n][2] for n in after), "updated_at must not change"
