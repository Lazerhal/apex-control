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
