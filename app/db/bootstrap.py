from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def ensure_schema_updates(conn: AsyncConnection) -> None:
    # Lightweight compatibility migration for local MVP before Alembic.
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS day_key VARCHAR(10) NOT NULL DEFAULT '1970-01-01'"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_images_used INTEGER NOT NULL DEFAULT 0"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_photo_analyses_used INTEGER NOT NULL DEFAULT 0"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_long_texts_used INTEGER NOT NULL DEFAULT 0"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_requests_used INTEGER NOT NULL DEFAULT 0"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_images_used INTEGER NOT NULL DEFAULT 0"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_photo_analyses_used INTEGER NOT NULL DEFAULT 0"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_long_texts_used INTEGER NOT NULL DEFAULT 0"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS pending_action VARCHAR(64)"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS bonus_image_credits INTEGER NOT NULL DEFAULT 0"))
