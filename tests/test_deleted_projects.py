"""A deleted project's tasks, notes and handoffs are gone, and unknown projects are 404."""
import asyncio

import pytest

from tests.test_projects import NOWHERE

HANDOFF = {"what_was_done": "a", "what_remains": "b", "next_model_should": "c"}
BODIES = {"tasks": {"title": "t"}, "notes": {"content": "n"}, "handoffs": HANDOFF}


async def contents(db):
    tables = ("tasks", "notes", "handoffs", "doc_sync_states")
    return {t: [dict(r) for r in await db.fetch(f"select * from {t} order by id")] for t in tables}


@pytest.mark.parametrize("kind", BODIES)
async def test_deleted_project_children_are_hidden_and_read_only(client, project, db, kind):
    url = f"/api/projects/{project['id']}/{kind}"
    assert (await client.post(url, json=BODIES[kind])).status_code == 201
    await client.delete(f"/api/projects/{project['id']}")
    before = await contents(db)
    assert (await client.get(url)).status_code == 404
    assert (await client.post(url, json=BODIES[kind])).status_code == 404
    assert await contents(db) == before


async def test_deleted_project_task_cannot_be_updated(client, project, db):
    url = f"/api/projects/{project['id']}/tasks"
    task = (await client.post(url, json={"title": "t"})).json()
    await client.delete(f"/api/projects/{project['id']}")
    before = await contents(db)
    res = await client.patch(f"{url}/{task['id']}", json={"status": "done"})
    assert res.status_code == 404
    assert await contents(db) == before


async def test_update_waits_for_a_delete_in_progress(client, project, db):
    url = f"/api/projects/{project['id']}/tasks"
    task = (await client.post(url, json={"title": "t"})).json()
    async with db.transaction():
        await db.execute("update projects set deleted_at = now()")
        pending = asyncio.create_task(client.patch(f"{url}/{task['id']}", json={"title": "late"}))
        done, _ = await asyncio.wait({pending}, timeout=0.5)
        assert not done, "the update did not wait for the delete"
    assert (await pending).status_code == 404
    assert await db.fetchval("select title from tasks") == "t"


@pytest.mark.parametrize("kind", BODIES)
async def test_unknown_project_is_404(client, kind):
    url = f"/api/projects/{NOWHERE}/{kind}"
    assert (await client.get(url)).status_code == 404
    assert (await client.post(url, json=BODIES[kind])).status_code == 404


@pytest.mark.parametrize("kind", BODIES)
async def test_existing_project_with_nothing_lists_empty(client, project, kind):
    res = await client.get(f"/api/projects/{project['id']}/{kind}")
    assert (res.status_code, res.json()) == (200, [])
