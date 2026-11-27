from types import SimpleNamespace

import httpx

from tests.conftest import BOT_TOKEN


async def test_status_uses_only_the_bot_header(monkeypatch):
    from src.telegram_bot import bot
    calls, replies = [], []

    def handler(request):
        calls.append((request.method, request.url.path, request.headers.get("x-bot-auth")))
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
    assert calls == [("GET", "/api/dashboard/summary", BOT_TOKEN)]
    assert replies[0].startswith("APEX Portfolio Summary")
