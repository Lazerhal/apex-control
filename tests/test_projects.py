import uuid

NOWHERE = "00000000-0000-0000-0000-000000000000"


async def test_create(client, db):
    res = await client.post("/api/projects", json={
        "name": "alpha", "type": "saas", "goal": "ship", "monthly_cost_usd": 12.5})
    body = res.json()
    assert res.status_code == 201
    assert body["apex_id"].startswith("APEX-SAAS-") and body["stage"] == "planning"
    assert body["monthly_cost_usd"] == 12.5 and body["goal"] == "ship"
    sync = await db.fetchrow("select sync_status from doc_sync_states where project_id = $1",
                             uuid.UUID(body["id"]))
    assert sync["sync_status"] == "in_sync"


async def test_create_requires_name_and_type(client):
    assert (await client.post("/api/projects", json={"name": "x"})).status_code == 422
    assert (await client.post("/api/projects", json={"type": "saas"})).status_code == 422


async def test_read_by_id_apex_id_and_list_filters(client, project):
    await client.post("/api/projects", json={"name": "beta", "type": "idea", "stage": "live"})
    assert (await client.get(f"/api/projects/{project['id']}")).json()["name"] == "demo"
    assert (await client.get(f"/api/projects/apex/{project['apex_id']}")).json()["id"] == project["id"]
    assert [p["name"] for p in (await client.get("/api/projects")).json()] == ["beta", "demo"]
    assert [p["name"] for p in (await client.get("/api/projects?stage=live")).json()] == ["beta"]
    assert [p["name"] for p in (await client.get("/api/projects?type=saas")).json()] == ["demo"]


async def test_update_changes_only_sent_fields(client, project):
    res = await client.patch(f"/api/projects/{project['id']}", json={"stage": "live", "goal": "g"})
    assert res.status_code == 200
    assert (res.json()["stage"], res.json()["goal"], res.json()["name"]) == ("live", "g", "demo")
    assert res.json()["updated_at"] > project["updated_at"]


async def test_delete_is_soft(client, project, db):
    res = await client.delete(f"/api/projects/{project['id']}")
    assert res.status_code == 200 and "demo" in res.json()["message"]
    assert (await client.get("/api/projects")).json() == []
    assert (await client.get(f"/api/projects/{project['id']}")).status_code == 404
    assert (await client.get(f"/api/projects/apex/{project['apex_id']}")).status_code == 404
    assert (await client.delete(f"/api/projects/{project['id']}")).status_code == 404
    assert await db.fetchval("select deleted_at is not null from projects")


async def test_unknown_project(client):
    assert (await client.get(f"/api/projects/{NOWHERE}")).status_code == 404
    assert (await client.patch(f"/api/projects/{NOWHERE}", json={})).status_code == 404
    assert (await client.delete(f"/api/projects/{NOWHERE}")).status_code == 404
    assert (await client.get("/api/projects/apex/NOPE")).status_code == 404
    assert (await client.get("/api/projects/not-a-uuid")).status_code == 422
