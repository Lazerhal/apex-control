"""Bugs found in existing code while writing the tests. Not fixed yet.

Each test states the correct behaviour and is marked as an expected failure. The marks are
strict: once a bug is fixed its test "unexpectedly passes" and fails the run, so remove the mark.
"""
import asyncio
import time

import pytest

from tests.conftest import DATABASE_URL, alembic
from tests.test_projects import NOWHERE


def bug(reason):
    return pytest.mark.xfail(reason=reason, raises=AssertionError, strict=True)


def tasks_url(project):
    return f"/api/projects/{project['id']}/tasks"


@bug("dashboard summary counts tasks of deleted projects")
async def test_summary_ignores_tasks_of_deleted_projects(client, project):
    await client.post(tasks_url(project), json={"title": "t", "priority": "critical"})
    await client.delete(f"/api/projects/{project['id']}")
    summary = (await client.get("/api/dashboard/summary")).json()
    assert summary["tasks"] == {"open": 0, "critical": 0}


@bug("tasks, notes and handoffs of a deleted project can still be listed")
@pytest.mark.parametrize("kind", ["tasks", "notes", "handoffs"])
async def test_deleted_project_children_are_hidden(client, project, kind):
    await client.delete(f"/api/projects/{project['id']}")
    assert (await client.get(f"/api/projects/{project['id']}/{kind}")).status_code == 404


@bug("a task of a deleted project can still be updated")
async def test_deleted_project_task_cannot_be_updated(client, project):
    task = (await client.post(tasks_url(project), json={"title": "t"})).json()
    await client.delete(f"/api/projects/{project['id']}")
    res = await client.patch(f"{tasks_url(project)}/{task['id']}", json={"status": "done"})
    assert res.status_code == 404


@bug("listing under an unknown project returns 200 and [] instead of 404")
@pytest.mark.parametrize("kind", ["tasks", "notes", "handoffs"])
async def test_listing_unknown_project_is_404(client, kind):
    assert (await client.get(f"/api/projects/{NOWHERE}/{kind}")).status_code == 404


@bug("values too long or too large for their column give 500 instead of 422")
@pytest.mark.parametrize("path,body", [
    ("/api/projects", {"name": "n" * 61, "type": "saas"}),
    ("/api/projects", {"name": "n", "type": "t" * 21}),
    ("/api/projects", {"name": "n", "type": "saas", "monthly_cost_usd": 1e9}),
    ("/api/ideas", {"title": "t" * 121, "raw_description": "d"}),
    ("{tasks}", {"title": "t" * 301}),
    ("{notes}", {"content": "x", "source": "s" * 51}),
], ids=["project-name", "project-type", "project-cost", "idea-title", "task-title", "note-source"])
async def test_oversized_values_are_rejected(client, project, path, body):
    base = f"/api/projects/{project['id']}"
    path = path.format(tasks=f"{base}/tasks", notes=f"{base}/notes")
    assert (await client.post(path, json=body)).status_code == 422


@bug("any string is accepted as a project type or stage")
@pytest.mark.parametrize("field", ["type", "stage"])
async def test_unknown_project_type_or_stage_is_rejected(client, field):
    body = {"name": "n", "type": "saas", field: "nonsense"}
    assert (await client.post("/api/projects", json=body)).status_code == 422


@bug("PATCH project with null for a required field gives 500")
@pytest.mark.parametrize("field", ["name", "stage"])
async def test_null_project_field_is_rejected(client, project, field):
    res = await client.patch(f"/api/projects/{project['id']}", json={field: None})
    assert res.status_code == 422


@bug("monthly_cost_usd: null is saved, after which listing ALL projects gives 500")
async def test_null_cost_does_not_break_the_project_list(client, project):
    await client.patch(f"/api/projects/{project['id']}", json={"monthly_cost_usd": None})
    assert (await client.get("/api/projects")).status_code == 200


@bug("PATCH task with an invalid value gives 500")
@pytest.mark.parametrize("body", [{"title": None}, {"title": "t" * 301}, {"completed_at": "yesterday"}],
                         ids=["null-title", "long-title", "bad-date"])
async def test_invalid_task_update_is_rejected(client, project, body):
    task = (await client.post(tasks_url(project), json={"title": "t"})).json()
    res = await client.patch(f"{tasks_url(project)}/{task['id']}", json=body)
    assert res.status_code == 422


@bug("reopening a done task keeps completed_at")
async def test_reopened_task_has_no_completion_time(client, project, db):
    task = (await client.post(tasks_url(project), json={"title": "t"})).json()
    for status in ("done", "open"):
        await client.patch(f"{tasks_url(project)}/{task['id']}", json={"status": status})
    assert await db.fetchval("select completed_at from tasks") is None


@bug("tasks created at the same time get the same apex_task_id")
async def test_concurrent_tasks_get_distinct_ids(client, project, db):
    async with db.transaction():
        # Lets every request count the tasks before any of them can insert
        await db.execute("lock table tasks in share mode")
        requests = [asyncio.create_task(client.post(tasks_url(project), json={"title": "t"}))
                    for _ in range(3)]
        await asyncio.sleep(1)
    ids = [r.json()["apex_task_id"] for r in await asyncio.gather(*requests)]
    assert len(set(ids)) == len(ids), ids


@pytest.fixture
def central_time(monkeypatch):
    monkeypatch.setenv("TZ", "America/Chicago")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


@bug("naive datetime.utcnow() values are stored shifted by the server's UTC offset")
@pytest.mark.parametrize("column", ["projects.deleted_at", "doc_sync_states.last_db_write",
                                    "tasks.completed_at"])
async def test_timestamps_are_right_outside_utc(client, project, db, central_time, column):
    task = (await client.post(tasks_url(project), json={"title": "t"})).json()
    await client.patch(f"{tasks_url(project)}/{task['id']}", json={"status": "done"})
    await client.post(f"/api/projects/{project['id']}/handoffs", json={
        "what_was_done": "a", "what_remains": "b", "next_model_should": "c"})
    await client.delete(f"/api/projects/{project['id']}")
    table, name = column.split(".")
    drift = await db.fetchval(f"select abs(extract(epoch from now() - {name})) from {table}")
    assert drift < 60, f"{column} is off by {float(drift) / 3600:.1f} hours"


@bug("Alembic fails when the database password contains % (for example URL-encoded characters)")
def test_migrations_accept_a_percent_encoded_password():
    # %65 is "e", so this is the same password, URL-encoded
    result = alembic("current", url=DATABASE_URL.replace(":test@", ":t%65st@"))
    assert "invalid interpolation syntax" not in result.stderr


@bug("the bot's help lists /note and /task, which have no handlers")
async def test_every_command_in_the_bot_help_exists():
    import re
    from types import SimpleNamespace
    from src.telegram_bot import bot
    replies = []

    async def reply(text):
        replies.append(text)

    await bot.cmd_start(SimpleNamespace(effective_user=SimpleNamespace(id=1),
                                        message=SimpleNamespace(reply_text=reply)), None)
    advertised = set(re.findall(r"^/(\w+)", replies[0], re.MULTILINE))
    handled = {c for h in bot.build_app().handlers[0] for c in getattr(h, "commands", ())}
    assert not advertised - handled, sorted(advertised - handled)
    assert advertised
