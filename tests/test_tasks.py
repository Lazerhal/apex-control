import asyncio

import pytest

from tests.test_projects import NOWHERE


def url(project, task_id=""):
    return f"/api/projects/{project['id']}/tasks" + (f"/{task_id}" if task_id else "")


async def test_create_and_list(client, project):
    first = await client.post(url(project), json={"title": "one", "priority": "critical"})
    second = await client.post(url(project), json={"title": "two"})
    assert first.status_code == second.status_code == 201
    assert (first.json()["apex_task_id"], second.json()["apex_task_id"]) == ("T-001", "T-002")
    assert second.json()["status"] == "open" and second.json()["priority"] == "medium"
    assert [t["title"] for t in (await client.get(url(project))).json()] == ["two", "one"]
    assert [t["title"] for t in (await client.get(url(project) + "?priority=critical")).json()] == ["one"]
    assert (await client.get(url(project) + "?status=done")).json() == []


async def test_update_and_complete(client, project, db):
    task = (await client.post(url(project), json={"title": "one"})).json()
    res = await client.patch(url(project, task["id"]), json={"title": "renamed", "status": "done"})
    assert res.status_code == 200
    assert (res.json()["title"], res.json()["status"]) == ("renamed", "done")
    assert await db.fetchval("select completed_at is not null from tasks")


async def test_not_found(client, project):
    assert (await client.post(f"/api/projects/{NOWHERE}/tasks", json={"title": "x"})).status_code == 404
    assert (await client.patch(url(project, NOWHERE), json={})).status_code == 404
    assert (await client.post(url(project), json={})).status_code == 422


async def test_task_cannot_be_updated_through_another_project(client, project):
    task = (await client.post(url(project), json={"title": "one"})).json()
    other = (await client.post("/api/projects", json={"name": "other", "type": "saas"})).json()
    assert (await client.patch(url(other, task["id"]), json={"title": "x"})).status_code == 404


async def new_task(client, project, **fields):
    res = await client.post(url(project), json={"title": "t", **fields})
    assert res.status_code == 201, res.text
    return res.json()


# ── Only listed fields can be changed ─────────────────────────────

async def test_every_editable_field(client, project, db):
    task = await new_task(client, project)
    changes = {"title": "new", "description": "d", "priority": "high", "type": "bug",
               "estimated_effort": "1d", "assigned_to": "me", "status": "blocked"}
    res = await client.patch(url(project, task["id"]), json={**changes, "blocked_by": ["x"]})
    assert res.status_code == 200, res.text
    assert {k: res.json()[k] for k in changes} == changes
    assert await db.fetchval("select blocked_by from tasks") == ["x"]
    cleared = await client.patch(url(project, task["id"]), json={
        "description": None, "estimated_effort": None, "assigned_to": None, "blocked_by": None})
    assert cleared.status_code == 200 and cleared.json()["title"] == "new"


@pytest.mark.parametrize("field,value", [
    ("id", NOWHERE), ("project_id", NOWHERE), ("created_at", "2000-01-01T00:00:00Z"),
    ("apex_task_id", "T-999"), ("updated_at", "2000-01-01T00:00:00Z"),
    ("completed_at", "2000-01-01T00:00:00Z"), ("parent_task_id", NOWHERE),
    ("project", "x"), ("metadata", {}), ("junk", 1),
])
async def test_other_fields_are_rejected_and_nothing_changes(client, project, db, field, value):
    task = await new_task(client, project)
    before = dict(await db.fetchrow("select * from tasks"))
    res = await client.patch(url(project, task["id"]), json={"title": "changed", field: value})
    assert res.status_code == 422, res.text
    assert dict(await db.fetchrow("select * from tasks")) == before


async def test_another_projects_id_cannot_take_over_a_task(client, project):
    other = (await client.post("/api/projects", json={"name": "other", "type": "saas"})).json()
    task = await new_task(client, project)
    res = await client.patch(url(project, task["id"]), json={"project_id": other["id"]})
    assert res.status_code == 422
    assert (await client.get(url(other))).json() == []


@pytest.mark.parametrize("body", [
    {"title": None}, {"status": None}, {"priority": None}, {"type": None},
    {"title": "t" * 301}, {"status": "s" * 21}, {"title": 5}, {"completed_at": "yesterday"}])
async def test_invalid_task_update_is_rejected(client, project, body):
    task = await new_task(client, project)
    assert (await client.patch(url(project, task["id"]), json=body)).status_code == 422


# ── completed_at follows the status ───────────────────────────────

@pytest.mark.parametrize("status", ["open", "in_progress", "blocked"])
async def test_reopened_task_has_no_completion_time(client, project, db, status):
    task = await new_task(client, project)
    await client.patch(url(project, task["id"]), json={"status": "done"})
    assert await db.fetchval("select completed_at from tasks") is not None
    await client.patch(url(project, task["id"]), json={"status": status})
    assert await db.fetchval("select completed_at from tasks") is None


async def test_editing_a_done_task_keeps_its_completion_time(client, project, db):
    task = await new_task(client, project)
    await client.patch(url(project, task["id"]), json={"status": "done"})
    completed = await db.fetchval("select completed_at from tasks")
    await client.patch(url(project, task["id"]), json={"title": "renamed"})
    assert await db.fetchval("select completed_at from tasks") == completed


# ── Task numbers ──────────────────────────────────────────────────

async def requests_waiting_on_locks(db) -> int:
    # A transaction keeps its first view of pg_stat_activity unless the snapshot is cleared
    await db.execute("select pg_stat_clear_snapshot()")
    return await db.fetchval("""
        select count(*) from pg_stat_activity
        where datname = current_database() and wait_event_type = 'Lock'""")


async def test_concurrent_tasks_get_distinct_ids(client, project, db):
    requests = []
    async with db.transaction():
        # Holds back every insert until all three requests are under way and waiting
        await db.execute("lock table tasks in share mode")
        requests = [asyncio.create_task(client.post(url(project), json={"title": "t"}))
                    for _ in range(3)]
        for _ in range(200):
            if await requests_waiting_on_locks(db) == 3:
                break
            await asyncio.sleep(0.05)
        else:
            raise TimeoutError("the three requests did not all reach a lock")
    responses = await asyncio.gather(*requests)
    assert sorted(r.json()["apex_task_id"] for r in responses) == ["T-001", "T-002", "T-003"]


async def test_many_concurrent_creates(client, project):
    responses = await asyncio.gather(*(client.post(url(project), json={"title": "t"})
                                       for _ in range(10)))
    assert sorted(r.json()["apex_task_id"] for r in responses) == [f"T-{n:03d}" for n in range(1, 11)]


async def test_numbering_is_per_project(client, project):
    other = (await client.post("/api/projects", json={"name": "other", "type": "saas"})).json()
    await new_task(client, project)
    assert (await new_task(client, other))["apex_task_id"] == "T-001"


async def test_numbering_continues_after_gaps_and_duplicates(client, project, db):
    for _ in range(3):
        await new_task(client, project)
    # What the old race left behind, plus a removed row and an unnumbered one
    await db.execute("update tasks set apex_task_id = 'T-007' where apex_task_id in ('T-002', 'T-003')")
    await db.execute("delete from tasks where apex_task_id = 'T-001'")
    assert (await new_task(client, project))["apex_task_id"] == "T-008"
    await db.execute("update tasks set apex_task_id = null")
    assert (await new_task(client, project))["apex_task_id"] == "T-001"
