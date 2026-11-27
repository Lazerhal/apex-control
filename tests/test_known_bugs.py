"""Bugs found in existing code while writing the tests. Not fixed yet.

Each test states the correct behaviour and is marked as an expected failure. The marks are
strict: once a bug is fixed its test "unexpectedly passes" and fails the run, so remove the mark.
"""
from urllib.parse import quote, unquote, urlsplit, urlunsplit

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


def with_encoded_password(url: str) -> str:
    """The same URL with the password's first character percent-encoded."""
    parts = urlsplit(url)
    password = unquote(parts.password)
    encoded = f"%{ord(password[0]):02X}" + quote(password[1:], safe="")
    userinfo, host = parts.netloc.rsplit("@", 1)
    result = urlunsplit(parts._replace(netloc=f"{userinfo.split(':', 1)[0]}:{encoded}@{host}"))
    assert encoded in result and unquote(urlsplit(result).password) == password
    return result


@bug("Alembic fails when the database password contains % (for example URL-encoded characters)")
def test_migrations_accept_a_percent_encoded_password():
    result = alembic("current", url=with_encoded_password(DATABASE_URL))
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
