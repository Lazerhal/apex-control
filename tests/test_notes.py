from tests.test_projects import NOWHERE


async def test_create_and_list(client, project):
    url = f"/api/projects/{project['id']}/notes"
    first = await client.post(url, json={"content": "first"})
    second = await client.post(url, json={"content": "second", "source": "telegram", "tags": ["a", "b"]})
    assert first.status_code == second.status_code == 201
    assert (first.json()["source"], first.json()["tags"]) == ("dashboard", [])
    assert second.json()["tags"] == ["a", "b"]
    assert [n["content"] for n in (await client.get(url)).json()] == ["second", "first"]


async def test_validation_and_not_found(client, project):
    assert (await client.post(f"/api/projects/{project['id']}/notes", json={})).status_code == 422
    res = await client.post(f"/api/projects/{NOWHERE}/notes", json={"content": "x"})
    assert res.status_code == 404
