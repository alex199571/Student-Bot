from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.crm import router as crm_router
from app.api.health import router as health_router
from app.api.telegram import router as telegram_router
from app.core.config import settings
from app.db.base import Base
from app.db.bootstrap import ensure_schema_updates
from app.db.session import engine
from app import models  # noqa: F401
from app.services.telegram_api import TelegramAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await ensure_schema_updates(conn)

    if settings.telegram_webhook_url:
        webhook_path = f"/telegram/webhook/{settings.telegram_webhook_secret}"
        webhook_url = f"{settings.telegram_webhook_url}{webhook_path}"
        telegram_api = TelegramAPI(settings.telegram_bot_token)
        await telegram_api.set_webhook(webhook_url)

    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health_router)
app.include_router(telegram_router)
app.include_router(admin_router)
app.include_router(crm_router)
