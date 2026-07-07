import logging
import os
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from src.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
OWNER_ID = int(settings.telegram_owner_chat_id)


def owner_only(func):
    """Decorator — silently drops messages not from owner."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or update.effective_user.id != OWNER_ID:
            logger.warning(f"Blocked message from non-owner: {update.effective_user}")
            return
        return await func(update, context)
    return wrapper


@owner_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "APEX Control Bot online.\n\n"
        "Commands:\n"
        "/status — portfolio summary\n"
        "/projects — list projects\n"
        "/note <project> <text> — add a note\n"
        "/task <project> <text> — add a task\n"
        "/idea <title> | <description> — log an idea\n"
        "/costs — cost summary\n"
        "/help — show this message"
    )


@owner_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            # Login to get token
            login = await client.post(
                "http://localhost:8001/auth/login",
                json={"username": settings.apex_dashboard_username,
                      "password": settings.apex_dashboard_password_hash},
                timeout=10
            )
            # Use internal bot auth instead
            summary_res = await client.get(
                "http://localhost:8001/api/dashboard/summary",
                headers={"X-Bot-Auth": settings.telegram_bot_token},
                timeout=10
            )
            if summary_res.status_code != 200:
                await update.message.reply_text("Could not reach APEX API.")
                return
            s = summary_res.json()
            proj = s["projects"]
            fin = s["financials"]
            tasks = s["tasks"]
            text = (
                f"APEX Portfolio Summary\n"
                f"{'='*28}\n"
                f"Projects: {proj['total']} total\n"
            )
            for stage, count in proj.get("by_stage", {}).items():
                text += f"  {stage}: {count}\n"
            text += (
                f"\nTasks: {tasks['open']} open, {tasks['critical']} critical\n"
                f"Ideas: {s['ideas']['new']} new\n"
                f"\nFinancials:\n"
                f"  Cost: ${fin['monthly_cost_usd']:.2f}/mo\n"
                f"  Revenue: ${fin['monthly_revenue_usd']:.2f}/mo\n"
                f"  P&L: ${fin['monthly_profit_usd']:.2f}/mo"
            )
            await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Status error: {e}")
        await update.message.reply_text(f"Error fetching status: {e}")


@owner_only
async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "http://localhost:8001/api/projects",
                headers={"X-Bot-Auth": settings.telegram_bot_token},
                timeout=10
            )
            if res.status_code != 200:
                await update.message.reply_text("Could not fetch projects.")
                return
            projects = res.json()
            lines = ["Active Projects\n" + "="*28]
            for p in projects:
                lines.append(
                    f"\n{p['name']} [{p['stage']}]\n"
                    f"  ID: {p['apex_id']}\n"
                    f"  Type: {p['type']}\n"
                    f"  Cost: ${p['monthly_cost_usd']}/mo"
                )
            await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


@owner_only
async def cmd_costs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "http://localhost:8001/api/projects",
                headers={"X-Bot-Auth": settings.telegram_bot_token},
                timeout=10
            )
            projects = res.json()
            total = sum(p["monthly_cost_usd"] for p in projects)
            lines = ["Monthly Costs\n" + "="*28]
            for p in projects:
                if p["monthly_cost_usd"] > 0:
                    lines.append(f"  {p['name']}: ${p['monthly_cost_usd']:.2f}")
            lines.append(f"\nTotal: ${total:.2f}/mo")
            lines.append(f"Annual: ${total*12:.2f}/yr")
            await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


@owner_only
async def cmd_idea(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import httpx
    text = " ".join(context.args) if context.args else ""
    if "|" not in text:
        await update.message.reply_text(
            "Usage: /idea <title> | <description>\n"
            "Example: /idea New tool | A calculator for X"
        )
        return
    parts = text.split("|", 1)
    title = parts[0].strip()
    description = parts[1].strip()
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "http://localhost:8001/api/ideas",
                headers={"X-Bot-Auth": settings.telegram_bot_token},
                json={"title": title, "raw_description": description, "source": "telegram"},
                timeout=10
            )
            if res.status_code == 201:
                idea = res.json()
                await update.message.reply_text(
                    f"Idea logged\n"
                    f"Title: {idea['title']}\n"
                    f"Status: {idea['status']}"
                )
            else:
                await update.message.reply_text(f"Failed to log idea: {res.status_code}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


@owner_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


@owner_only
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Unknown command. Send /help for available commands."
    )


def build_app() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("projects", cmd_projects))
    app.add_handler(CommandHandler("costs", cmd_costs))
    app.add_handler(CommandHandler("idea", cmd_idea))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    return app


def run():
    logger.info(f"Starting APEX Telegram bot (owner: {OWNER_ID})")
    app = build_app()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    run()
