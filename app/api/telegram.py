from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.telegram import TelegramUpdate
from app.services.bot_logic import BotService
from app.services.telegram_api import TelegramAPI

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook/{secret}")
async def telegram_webhook(secret: str, update: TelegramUpdate, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")

    bot = BotService(db=db, telegram_api=TelegramAPI(settings.telegram_bot_token))
    await bot.handle_update(update)
    return {"ok": True}
