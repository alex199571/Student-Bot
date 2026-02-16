from app.db.redis import redis_client


PENDING_KEY_PREFIX = "pending_action"
PENDING_TTL_SECONDS = 600


def _pending_key(telegram_id: int) -> str:
    return f"{PENDING_KEY_PREFIX}:{telegram_id}"


async def set_pending_action(telegram_id: int, action: str) -> None:
    await redis_client.set(_pending_key(telegram_id), action, ex=PENDING_TTL_SECONDS)


async def get_pending_action(telegram_id: int) -> str | None:
    return await redis_client.get(_pending_key(telegram_id))


async def clear_pending_action(telegram_id: int) -> None:
    await redis_client.delete(_pending_key(telegram_id))
