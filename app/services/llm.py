import base64
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.core.i18n import t


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str


@dataclass
class ImageResult:
    image_bytes: bytes
    mime_type: str
    model: str


class LLMService:
    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.image_model = settings.openai_image_model
        self.base_url = "https://api.openai.com/v1/responses"
        self.image_url = "https://api.openai.com/v1/images/generations"

    def estimate_tokens(self, text: str) -> int:
        # Approximation suitable for pre-check before real provider usage report.
        return max(1, len(text) // 4)

    async def generate(self, system_prompt: str, user_prompt: str, max_output_tokens: int, lang: str) -> LLMResult:
        if not self.api_key:
            message = t("generic_answer", lang)
            in_tokens = self.estimate_tokens(system_prompt + user_prompt)
            out_tokens = min(self.estimate_tokens(message), max_output_tokens)
            return LLMResult(
                text=message,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                total_tokens=in_tokens + out_tokens,
                model="fallback-no-key",
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
            "max_output_tokens": max_output_tokens,
        }

        async with httpx.AsyncClient(timeout=40) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        text = data.get("output_text")
        if not text:
            text = self._extract_text(data)

        usage = data.get("usage", {})
        input_tokens = int(usage.get("input_tokens", self.estimate_tokens(system_prompt + user_prompt)))
        output_tokens = int(usage.get("output_tokens", self.estimate_tokens(text)))
        total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens))

        return LLMResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model=data.get("model", self.model),
        )

    async def generate_image(self, prompt: str) -> ImageResult:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.image_model,
            "prompt": prompt,
            "size": "1024x1024",
        }

        async with httpx.AsyncClient(timeout=80) as client:
            response = await client.post(self.image_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        item = (data.get("data") or [{}])[0]
        b64 = item.get("b64_json")
        if not b64:
            raise RuntimeError("Image provider returned no b64_json")

        return ImageResult(
            image_bytes=base64.b64decode(b64),
            mime_type="image/png",
            model=data.get("model", self.image_model),
        )

    async def analyze_photo(self, image_url: str, user_prompt: str, max_output_tokens: int, lang: str) -> LLMResult:
        if not self.api_key:
            message = t("generic_answer", lang)
            in_tokens = self.estimate_tokens(user_prompt) + 200
            out_tokens = min(self.estimate_tokens(message), max_output_tokens)
            return LLMResult(
                text=message,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                total_tokens=in_tokens + out_tokens,
                model="fallback-no-key",
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": "You analyze educational images for students."}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_prompt},
                        {"type": "input_image", "image_url": image_url},
                    ],
                },
            ],
            "max_output_tokens": max_output_tokens,
        }

        async with httpx.AsyncClient(timeout=80) as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        text = data.get("output_text") or self._extract_text(data)
        usage = data.get("usage", {})
        input_tokens = int(usage.get("input_tokens", self.estimate_tokens(user_prompt) + 300))
        output_tokens = int(usage.get("output_tokens", self.estimate_tokens(text)))
        total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens))

        return LLMResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model=data.get("model", self.model),
        )

    @staticmethod
    def _extract_text(payload: dict) -> str:
        output = payload.get("output", [])
        chunks: list[str] = []
        for item in output:
            for content_item in item.get("content", []):
                if content_item.get("type") == "output_text":
                    chunks.append(content_item.get("text", ""))
        return "\n".join(part for part in chunks if part).strip() or "No response text returned."
