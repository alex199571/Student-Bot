from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    plan: Mapped[str] = mapped_column(String(16), default="free", nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    month_key: Mapped[str] = mapped_column(String(7), default="1970-01", nullable=False)
    monthly_requests_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_images_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_photo_analyses_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_long_texts_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bonus_image_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
