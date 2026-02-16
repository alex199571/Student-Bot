from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.limits import month_key_now


HEADERS = [
    "telegram_id",
    "username",
    "first_name",
    "language",
    "plan",
    "is_banned",
    "monthly_requests_used",
    "monthly_tokens_used",
    "monthly_images_used",
    "monthly_photo_analyses_used",
    "monthly_long_texts_used",
    "bonus_image_credits",
    "month_key",
]


@dataclass
class SyncResult:
    pulled_updated: int = 0
    pulled_created: int = 0
    pushed_rows: int = 0


class GoogleSheetsSyncService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)

    def _open_worksheet(self):
        if not settings.google_sheets_id:
            raise RuntimeError("GOOGLE_SHEETS_ID is empty")

        credentials_path = Path(settings.google_service_account_file)
        if not credentials_path.exists():
            raise RuntimeError(f"Service account file not found: {credentials_path}")

        creds = Credentials.from_service_account_file(
            str(credentials_path),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(settings.google_sheets_id)
        return spreadsheet.worksheet(settings.google_sheets_worksheet)

    @staticmethod
    def _bool_from_string(value: str | None) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "y"}

    @staticmethod
    def _int_from_string(value: str | None, default: int = 0) -> int:
        try:
            return int(str(value or "").strip())
        except Exception:
            return default

    @staticmethod
    def _normalize_plan(value: str | None) -> str:
        plan = (value or "free").strip().lower()
        if plan == "paid":
            return "pro"
        if plan not in {"free", "student", "pro"}:
            return "free"
        return plan

    def _user_to_row(self, u: User) -> list[str]:
        return [
            str(u.telegram_id),
            u.username or "",
            u.first_name or "",
            u.language,
            self._normalize_plan(u.plan),
            "true" if u.is_banned else "false",
            str(u.monthly_requests_used),
            str(u.monthly_tokens_used),
            str(u.monthly_images_used),
            str(u.monthly_photo_analyses_used),
            str(u.monthly_long_texts_used),
            str(u.bonus_image_credits),
            u.month_key,
        ]

    async def pull_from_sheets(self) -> SyncResult:
        ws = self._open_worksheet()
        rows = ws.get_all_values()
        if not rows:
            ws.append_row(HEADERS)
            return SyncResult()

        header = [h.strip() for h in rows[0]]
        if header != HEADERS:
            ws.clear()
            ws.append_row(HEADERS)
            rows = [HEADERS]

        result = SyncResult()

        for raw in rows[1:]:
            if not raw:
                continue
            raw = list(raw) + [""] * (len(HEADERS) - len(raw))
            data = dict(zip(HEADERS, raw))

            telegram_id = self._int_from_string(data.get("telegram_id"), default=0)
            if telegram_id <= 0:
                continue

            user = await self.users.get_by_telegram_id(telegram_id)
            if not user:
                user = User(
                    telegram_id=telegram_id,
                    username=(data.get("username") or "") or None,
                    first_name=(data.get("first_name") or "") or None,
                    language=(data.get("language") or "en")[:8],
                    plan=self._normalize_plan(data.get("plan")),
                    is_banned=self._bool_from_string(data.get("is_banned")),
                    month_key=(data.get("month_key") or month_key_now())[:7],
                    monthly_requests_used=self._int_from_string(data.get("monthly_requests_used")),
                    monthly_tokens_used=self._int_from_string(data.get("monthly_tokens_used")),
                    monthly_images_used=self._int_from_string(data.get("monthly_images_used")),
                    monthly_photo_analyses_used=self._int_from_string(data.get("monthly_photo_analyses_used")),
                    monthly_long_texts_used=self._int_from_string(data.get("monthly_long_texts_used")),
                    bonus_image_credits=self._int_from_string(data.get("bonus_image_credits")),
                )
                await self.users.save(user)
                result.pulled_created += 1
                continue

            updated = False

            next_username = (data.get("username") or "") or None
            if user.username != next_username:
                user.username = next_username
                updated = True

            next_first_name = (data.get("first_name") or "") or None
            if user.first_name != next_first_name:
                user.first_name = next_first_name
                updated = True

            next_language = (data.get("language") or user.language)[:8]
            if next_language and user.language != next_language:
                user.language = next_language
                updated = True

            next_plan = self._normalize_plan(data.get("plan"))
            if user.plan != next_plan:
                user.plan = next_plan
                updated = True

            next_banned = self._bool_from_string(data.get("is_banned"))
            if user.is_banned != next_banned:
                user.is_banned = next_banned
                updated = True

            next_month_key = (data.get("month_key") or user.month_key)[:7]
            if next_month_key and user.month_key != next_month_key:
                user.month_key = next_month_key
                updated = True

            int_fields = {
                "monthly_requests_used": "monthly_requests_used",
                "monthly_tokens_used": "monthly_tokens_used",
                "monthly_images_used": "monthly_images_used",
                "monthly_photo_analyses_used": "monthly_photo_analyses_used",
                "monthly_long_texts_used": "monthly_long_texts_used",
                "bonus_image_credits": "bonus_image_credits",
            }
            for col, attr in int_fields.items():
                new_val = self._int_from_string(data.get(col), default=getattr(user, attr))
                if getattr(user, attr) != new_val:
                    setattr(user, attr, new_val)
                    updated = True

            if updated:
                await self.users.save(user)
                result.pulled_updated += 1

        await self.db.commit()
        return result

    async def push_to_sheets(self) -> SyncResult:
        ws = self._open_worksheet()
        users = await self.users.list_all_users()

        values = ws.get_all_values()
        if not values:
            ws.append_row(HEADERS)
            values = [HEADERS]

        header = [h.strip() for h in values[0]]
        if header != HEADERS:
            ws.clear()
            ws.append_row(HEADERS)
            values = [HEADERS]

        rows = [HEADERS] + [self._user_to_row(u) for u in users]
        ws.clear()
        ws.update("A1", rows, value_input_option="RAW")

        return SyncResult(pushed_rows=len(users))

    async def sync_both(self) -> SyncResult:
        pulled = await self.pull_from_sheets()
        pushed = await self.push_to_sheets()
        return SyncResult(
            pulled_updated=pulled.pulled_updated,
            pulled_created=pulled.pulled_created,
            pushed_rows=pushed.pushed_rows,
        )
