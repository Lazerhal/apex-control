from tests.test_projects import NOWHERE


async def test_create_list_and_read(client):
    res = await client.post("/api/ideas", json={"title": "one", "raw_description": "d"})
    assert res.status_code == 201
    assert (res.json()["status"], res.json()["source"]) == ("new", "dashboard")
    await client.post("/api/ideas", json={"title": "two", "raw_description": "d", "source": "telegram"})
    assert [i["title"] for i in (await client.get("/api/ideas")).json()] == ["two", "one"]
    assert (await client.get("/api/ideas?status=archived")).json() == []
    assert (await client.get(f"/api/ideas/{res.json()['id']}")).json()["title"] == "one"


async def test_soft_deleted_ideas_are_hidden(client, db):
    idea = (await client.post("/api/ideas", json={"title": "t", "raw_description": "d"})).json()
    await db.execute("update ideas set deleted_at = now()")
    assert (await client.get("/api/ideas")).json() == []
    assert (await client.get(f"/api/ideas/{idea['id']}")).status_code == 404


async def test_validation_and_not_found(client):
    assert (await client.post("/api/ideas", json={"title": "t"})).status_code == 422
    assert (await client.get(f"/api/ideas/{NOWHERE}")).status_code == 404
