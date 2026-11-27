"""Bad input gets a 422, never a 500, and nothing is stored."""
import json

import pytest

from tests.conftest import PASSWORD, USERNAME

HANDOFF = {"what_was_done": "a", "what_remains": "b", "next_model_should": "c"}
# Where to POST, a body that is accepted, and the longest value of each limited field
CREATES = {
    "projects": ("/api/projects", {"name": "n", "type": "saas"}, {
        "name": 60, "live_url": 500, "github_repo": 500, "repo_visibility": 10,
        "primary_branch": 50, "local_path": 500}),
    "tasks": ("{project}/tasks", {"title": "t"}, {
        "title": 300, "priority": 20, "type": 30, "estimated_effort": 20, "assigned_to": 100}),
    "notes": ("{project}/notes", {"content": "c"}, {"source": 50}),
    "handoffs": ("{project}/handoffs", HANDOFF, {"session_tool": 100}),
    "ideas": ("/api/ideas", {"title": "t", "raw_description": "d"}, {"title": 120, "source": 50}),
    "events": ("/api/events", {"kind": "k", "source": "s"}, {
        "kind": 50, "source": 30, "target": 50, "actor": 50, "status": 20}),
}
LIMITS = [(kind, field, size) for kind, (_, _, fields) in CREATES.items()
          for field, size in fields.items()]
PROJECT_PATCH_LIMITS = {"name": 60, "live_url": 500, "github_repo": 500, "cost_efficiency_flag": 20}
TASK_PATCH_LIMITS = {"title": 300, "priority": 20, "type": 30, "estimated_effort": 20,
                     "assigned_to": 100, "status": 20}
JSON = {"Content-Type": "application/json"}
TABLES = ("projects", "tasks", "notes", "handoffs", "ideas")


def base(project):
    return f"/api/projects/{project['id']}"


async def stored(db):
    return {t: [str(dict(r)) for r in await db.fetch(f"select * from {t} order by id")]
            for t in TABLES}


@pytest.mark.parametrize("kind,field,size", LIMITS)
async def test_length_limits_on_create(client, project, kind, field, size):
    path, body, _ = CREATES[kind]
    url = path.format(project=base(project))
    # Multi-byte characters: the limit counts characters, as the database does
    longest = await client.post(url, json={**body, field: "\u00e9" * size})
    assert longest.status_code == 201, longest.text
    too_long = await client.post(url, json={**body, field: "n" * (size + 1)})
    assert too_long.status_code == 422, too_long.text


@pytest.mark.parametrize("field,size", PROJECT_PATCH_LIMITS.items())
async def test_length_limits_on_project_update(client, project, field, size):
    assert (await client.patch(base(project), json={field: "n" * size})).status_code == 200
    assert (await client.patch(base(project), json={field: "n" * (size + 1)})).status_code == 422


@pytest.mark.parametrize("field,size", TASK_PATCH_LIMITS.items())
async def test_length_limits_on_task_update(client, project, field, size):
    task = (await client.post(f"{base(project)}/tasks", json={"title": "t"})).json()
    url = f"{base(project)}/tasks/{task['id']}"
    assert (await client.patch(url, json={field: "n" * size})).status_code == 200
    assert (await client.patch(url, json={field: "n" * (size + 1)})).status_code == 422


@pytest.mark.parametrize("field", ["monthly_cost_usd", "monthly_revenue_usd"])
@pytest.mark.parametrize("value,accepted", [
    (99_999_999.99, True), (-99_999_999.99, True), (99_999_999.995, False), (1e8, False),
    (-1e8, False), (1e300, False), (10 ** 400, False)])
async def test_amount_limits(client, project, field, value, accepted):
    created = await client.post("/api/projects", json={"name": "n", "type": "saas", field: value})
    patched = await client.patch(base(project), json={field: value})
    expected = (201, 200) if accepted else (422, 422)
    assert (created.status_code, patched.status_code) == expected
    assert (await client.get("/api/dashboard/summary")).status_code == 200


@pytest.mark.parametrize("field,value,accepted", [
    ("cost_usd", 9_999.999999, True), ("cost_usd", 9_999.9999999, False),
    ("cost_usd", 10_000, False), ("latency_ms", 2_147_483_647, True),
    ("latency_ms", 2_147_483_648, False)])
async def test_event_number_limits(client, field, value, accepted):
    res = await client.post("/api/events", json={"kind": "k", "source": "s", field: value})
    assert res.status_code == (201 if accepted else 422), res.text


REQUIRED = {
    "projects": ["name", "type", "stage", "primary_branch", "monthly_cost_usd",
                 "monthly_revenue_usd"],
    "tasks": ["title", "priority", "type"],
    "notes": ["content", "source", "tags"],
    "handoffs": ["what_was_done", "what_remains", "what_is_blocked", "next_model_should"],
    "ideas": ["title", "raw_description", "source"],
    "events": ["kind", "source", "status", "payload"],
}


@pytest.mark.parametrize("kind,field", [(k, f) for k, fields in REQUIRED.items() for f in fields])
async def test_null_in_a_required_field_on_create(client, project, db, kind, field):
    path, body, _ = CREATES[kind]
    before = await stored(db)
    res = await client.post(path.format(project=base(project)), json={**body, field: None})
    assert res.status_code == 422, res.text
    assert await stored(db) == before


@pytest.mark.parametrize("field", ["name", "stage", "monthly_cost_usd", "monthly_revenue_usd",
                                   "cost_efficiency_flag"])
async def test_null_in_a_required_project_field(client, project, db, field):
    before = await stored(db)
    res = await client.patch(base(project), json={field: None})
    assert res.status_code == 422 and "cannot be null" in res.text
    assert await stored(db) == before


async def test_optional_project_fields_can_be_cleared(client, project):
    res = await client.patch(base(project), json={
        "short_description": None, "goal": None, "status_note": None, "live_url": None,
        "github_repo": None})
    assert res.status_code == 200


TYPES = ["product-tool", "content-engine", "saas", "governed-system", "infrastructure", "idea"]
STAGES = ["idea", "planning", "active-development", "live", "paused", "retired"]


@pytest.mark.parametrize("project_type", TYPES)
async def test_every_project_type_is_accepted(client, project_type):
    res = await client.post("/api/projects", json={"name": "n", "type": project_type})
    assert res.status_code == 201 and res.json()["type"] == project_type
    assert "-PROJ-" not in res.json()["apex_id"]


@pytest.mark.parametrize("stage", STAGES)
async def test_every_stage_is_accepted(client, project, stage):
    created = await client.post("/api/projects", json={"name": "n", "type": "saas", "stage": stage})
    patched = await client.patch(base(project), json={"stage": stage})
    assert (created.status_code, patched.status_code) == (201, 200)
    assert created.json()["stage"] == patched.json()["stage"] == stage


@pytest.mark.parametrize("value", ["nonsense", "", "SaaS", "Live", "t" * 40, 1])
async def test_other_types_and_stages_are_rejected(client, project, db, value):
    before = await stored(db)
    responses = [
        await client.post("/api/projects", json={"name": "n", "type": value}),
        await client.post("/api/projects", json={"name": "n", "type": "saas", "stage": value}),
        await client.patch(base(project), json={"stage": value})]
    assert [r.status_code for r in responses] == [422, 422, 422]
    assert await stored(db) == before


async def test_rows_with_other_types_and_stages_can_still_be_read_and_edited(client, project, db):
    await db.execute("update projects set type = 'legacy', stage = 'old'")
    assert (await client.get("/api/projects?stage=old&type=legacy")).json()[0]["stage"] == "old"
    assert (await client.patch(base(project), json={"goal": "g"})).status_code == 200


# Text the database cannot store: a null character, and half of a surrogate pair
BAD_TEXT = ["a\\u0000b", "a\\ud800b"]


@pytest.mark.parametrize("bad", BAD_TEXT, ids=["null-character", "surrogate"])
@pytest.mark.parametrize("kind,field", [
    ("projects", "name"), ("projects", "goal"), ("tasks", "title"), ("tasks", "description"),
    ("notes", "content"), ("handoffs", "what_was_done"), ("ideas", "raw_description"),
    ("events", "kind")])
async def test_unstorable_text_on_create(client, project, db, kind, field, bad):
    path, body, _ = CREATES[kind]
    raw = json.dumps({**body, field: "PLACEHOLDER"}).replace("PLACEHOLDER", bad)
    before = await stored(db)
    res = await client.post(path.format(project=base(project)), content=raw, headers=JSON)
    assert res.status_code == 422, res.text
    assert await stored(db) == before


@pytest.mark.parametrize("bad", BAD_TEXT, ids=["null-character", "surrogate"])
async def test_unstorable_text_in_lists_payloads_and_updates(client, project, db, bad):
    task = (await client.post(f"{base(project)}/tasks", json={"title": "t"})).json()
    before = await stored(db)
    for method, url, raw in [
        ("POST", f"{base(project)}/notes", '{"content": "c", "tags": ["X"]}'),
        ("PATCH", f"{base(project)}/tasks/{task['id']}", '{"blocked_by": ["X"]}'),
        ("PATCH", f"{base(project)}/tasks/{task['id']}", '{"title": "X"}'),
        ("PATCH", base(project), '{"goal": "X"}'),
        ("POST", "/api/events", '{"kind": "k", "source": "s", "payload": {"a": ["X"]}}'),
        ("POST", "/api/events", '{"kind": "k", "source": "s", "payload": {"X": 1}}'),
        ("POST", "/auth/login", '{"username": "X", "password": "p"}'),
        ("POST", "/auth/login", f'{{"username": "{USERNAME}", "password": "X"}}'),
    ]:
        res = await client.request(method, url, content=raw.replace("X", bad), headers=JSON)
        assert res.status_code == 422, (method, url, raw, res.text)
    assert await stored(db) == before


@pytest.mark.parametrize("number", ["NaN", "Infinity", "1e400"])
async def test_non_finite_numbers_in_an_event_payload(client, number):
    raw = f'{{"kind": "k", "source": "s", "payload": {{"a": [{number}]}}}}'
    assert (await client.post("/api/events", content=raw, headers=JSON)).status_code == 422


@pytest.mark.parametrize("url", [
    "/api/projects?stage=%00", "/api/projects?type=%00", "/api/projects/apex/%00",
    "{project}/tasks?status=%00", "{project}/tasks?priority=%00", "/api/ideas?status=%00",
    "/api/events?kind=%00"])
async def test_null_character_in_a_url(client, project, url):
    assert (await client.get(url.format(project=base(project)))).status_code == 422


@pytest.mark.parametrize("content,content_type", [
    (b"\xff\xfe", "text/plain"), (b"plain", "text/plain"), (b'"a\\ud800"', "application/json")])
@pytest.mark.parametrize("url", ["/api/projects", "/api/ideas", "/auth/login"])
async def test_bodies_that_are_not_an_object(client, url, content, content_type):
    res = await client.post(url, content=content, headers={"Content-Type": content_type})
    assert res.status_code == 422, res.text


async def test_oversized_password(anon):
    res = await anon.post("/auth/login", json={"username": USERNAME, "password": "p" * 4097})
    assert res.status_code == 422
    ok = await anon.post("/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert ok.status_code == 200


@pytest.mark.parametrize("depth", [100, 500, 900])
@pytest.mark.parametrize("url,field", [
    ("/api/projects", "name"), ("/api/events", "payload"), ("/auth/login", "password")])
async def test_deeply_nested_input(client, url, field, depth):
    body = {"name": "n", "type": "saas", "kind": "k", "source": "s", "username": "u"}
    nested = '{"a":' * depth + "1" + "}" * depth
    raw = json.dumps({**body, field: "PLACEHOLDER"}).replace('"PLACEHOLDER"', nested)
    res = await client.post(url, content=raw, headers=JSON)
    assert res.status_code == 422, res.text
    assert (await client.get("/api/events")).status_code == 200


async def test_payload_depth_limit(client):
    def nested(depth):
        return {"a": nested(depth - 1)} if depth else 1

    body = {"kind": "k", "source": "s"}
    assert (await client.post("/api/events", json={**body, "payload": nested(32)})).status_code == 201
    assert (await client.post("/api/events", json={**body, "payload": nested(33)})).status_code == 422
    assert (await client.get("/api/events")).status_code == 200
