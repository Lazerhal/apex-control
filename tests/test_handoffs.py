from datetime import date

from tests.test_projects import NOWHERE

BODY = {"what_was_done": "a", "what_remains": "b", "next_model_should": "c"}


async def test_create_and_list(client, project, db):
    url = f"/api/projects/{project['id']}/handoffs"
    res = await client.post(url, json=BODY)
    assert res.status_code == 201, res.text
    assert res.json()["session_date"] == str(date.today())
    assert res.json()["what_is_blocked"] == "Nothing"
    listed = (await client.get(url)).json()
    assert [h["id"] for h in listed] == [res.json()["id"]]
    assert await db.fetchval("select sync_status from doc_sync_states") == "db_ahead"


async def test_list_returns_the_latest_ten(client, project):
    url = f"/api/projects/{project['id']}/handoffs"
    for n in range(12):
        await client.post(url, json={**BODY, "what_was_done": str(n)})
    listed = (await client.get(url)).json()
    assert [h["what_was_done"] for h in listed] == [str(n) for n in range(11, 1, -1)]


async def test_validation_and_not_found(client, project):
    assert (await client.post(f"/api/projects/{project['id']}/handoffs", json={})).status_code == 422
    assert (await client.post(f"/api/projects/{NOWHERE}/handoffs", json=BODY)).status_code == 404
