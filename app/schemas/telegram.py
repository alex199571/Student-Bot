from typing import Any

from pydantic import BaseModel, Field


class TelegramUser(BaseModel):
    id: int
    is_bot: bool | None = None
    first_name: str | None = None
    username: str | None = None
    language_code: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str | None = None


class TelegramPhotoSize(BaseModel):
    file_id: str
    file_unique_id: str | None = None
    width: int | None = None
    height: int | None = None
    file_size: int | None = None


class TelegramMessage(BaseModel):
    message_id: int
    from_: TelegramUser | None = Field(default=None, alias="from")
    chat: TelegramChat
    text: str | None = None
    caption: str | None = None
    photo: list[TelegramPhotoSize] | None = None

    model_config = {"populate_by_name": True, "from_attributes": True}


class CallbackQuery(BaseModel):
    id: str
    from_: TelegramUser = Field(alias="from")
    data: str | None = None
    message: TelegramMessage | None = None

    model_config = {"populate_by_name": True, "from_attributes": True}


class TelegramUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None
    callback_query: CallbackQuery | None = None


class TelegramResponse(BaseModel):
    ok: bool
    result: Any | None = None
