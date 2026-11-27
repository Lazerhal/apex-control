import re
from types import SimpleNamespace

import httpx
import pytest

from tests.conftest import INTERNAL_KEY


async def test_status_uses_only_the_bot_header(monkeypatch):
    from src.telegram_bot import bot
    calls, replies = [], []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={
            "projects": {"total": 1, "by_stage": {"live": 1}}, "tasks": {"open": 0, "critical": 0},
            "ideas": {"new": 0}, "financials": {
                "monthly_cost_usd": 0, "monthly_revenue_usd": 0, "monthly_profit_usd": 0}})

    real = httpx.AsyncClient
    # Every request goes to the mock: the bot's URL is the live API's address
    monkeypatch.setattr(httpx, "AsyncClient", lambda: real(transport=httpx.MockTransport(handler)))

    async def reply(text):
        replies.append(text)

    update = SimpleNamespace(effective_user=SimpleNamespace(id=1),
                             message=SimpleNamespace(reply_text=reply))
    await bot.cmd_status(update, None)
    (request,) = calls
    assert (request.method, request.url.path) == ("GET", "/api/dashboard/summary")
    assert request.headers["x-bot-auth"] == INTERNAL_KEY
    assert "authorization" not in request.headers and "cookie" not in request.headers
    assert replies[0].startswith("APEX Portfolio Summary")


@pytest.mark.parametrize("command,args", [
    ("cmd_status", []), ("cmd_projects", []), ("cmd_costs", []), ("cmd_idea", ["t", "|", "d"])])
async def test_every_api_command_authenticates(monkeypatch, app, command, args):
    """The real API accepts what each command sends."""
    from src.telegram_bot import bot
    statuses, replies = [], []
    real = httpx.AsyncClient

    async def record(response):
        statuses.append(response.status_code)

    monkeypatch.setattr(httpx, "AsyncClient", lambda: real(
        transport=httpx.ASGITransport(app=app), event_hooks={"response": [record]}))

    async def reply(text):
        replies.append(text)

    update = SimpleNamespace(effective_user=SimpleNamespace(id=1),
                             message=SimpleNamespace(reply_text=reply))
    await getattr(bot, command)(update, SimpleNamespace(args=args))
    assert len(statuses) == 1 and statuses[0] in (200, 201), (statuses, replies)


def test_bot_refuses_to_run_without_the_internal_key(monkeypatch):
    from src.telegram_bot import bot
    monkeypatch.setattr(bot.settings, "apex_internal_key", "")
    monkeypatch.setattr(bot, "build_app", lambda: pytest.fail("the bot started"))
    with pytest.raises(SystemExit, match="APEX_INTERNAL_KEY"):
        bot.run()


async def test_every_command_in_the_bot_help_exists():
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
