# apex-control

The main APEX application. Contains the FastAPI backend, Next.js dashboard, background workers, APScheduler, Telegram bot, model router, doc engine, machine control, UPS safety, and integration ingestors.

**See [apex-core](https://github.com/Lazerhal/apex-core) for shared schemas and tooling.**

## Services
- `src/api/` — FastAPI REST API
- `src/worker/` — Background job workers
- `src/scheduler/` — APScheduler with SQLAlchemyJobStore
- `src/telegram_bot/` — Telegram control interface
- `src/model_router/` — AI model routing and cost tracking
- `src/doc_engine/` — Markdown parser, validator, sync engine
- `src/machine_control/` — Build node mode switching
- `src/power_safety/` — UPS monitoring and safe shutdown
- `src/ingestors/` — External service data collectors
- `src/dashboard/` — Next.js frontend (panelised)
