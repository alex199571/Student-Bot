import httpx

from app.schemas.telegram import TelegramResponse


class TelegramAPI:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    async def set_webhook(self, webhook_url: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{self.base_url}/setWebhook", json={"url": webhook_url})

    async def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None) -> TelegramResponse:
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(f"{self.base_url}/sendMessage", json=payload)
            response.raise_for_status()
            return TelegramResponse(**response.json())

    async def answer_callback_query(self, callback_query_id: str) -> None:
        payload = {"callback_query_id": callback_query_id}
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"{self.base_url}/answerCallbackQuery", json=payload)

    async def send_photo_bytes(
        self,
        chat_id: int,
        image_bytes: bytes,
        filename: str = "image.png",
        caption: str | None = None,
    ) -> TelegramResponse:
        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption

        files = {"photo": (filename, image_bytes, "image/png")}

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self.base_url}/sendPhoto", data=data, files=files)
            response.raise_for_status()
            return TelegramResponse(**response.json())

    async def get_file_download_url(self, file_id: str) -> str:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/getFile", params={"file_id": file_id})
            response.raise_for_status()
            payload = TelegramResponse(**response.json())

        file_path = (payload.result or {}).get("file_path")
        if not file_path:
            raise RuntimeError("Telegram getFile did not return file_path")

        return f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
