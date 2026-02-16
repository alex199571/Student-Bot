from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.query_log import QueryLog


class QueryLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        telegram_id: int,
        action: str,
        plan: str,
        prompt_text: str,
        status: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        response_text: str | None = None,
        error_message: str | None = None,
    ) -> QueryLog:
        item = QueryLog(
            telegram_id=telegram_id,
            action=action,
            plan=plan,
            prompt_text=prompt_text,
            response_text=response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            status=status,
            error_message=error_message,
        )
        self.db.add(item)
        await self.db.flush()
        return item

    async def list_logs(self, limit: int, offset: int, telegram_id: int | None = None) -> list[QueryLog]:
        query = select(QueryLog).order_by(QueryLog.id.desc()).limit(limit).offset(offset)
        if telegram_id is not None:
            query = query.where(QueryLog.telegram_id == telegram_id)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_stats(self) -> dict[str, int]:
        query = select(
            func.count(QueryLog.id).label("total_logs"),
            func.sum(case((QueryLog.status == "ok", 1), else_=0)).label("ok_logs"),
            func.sum(case((QueryLog.status == "error", 1), else_=0)).label("error_logs"),
            func.sum(case((QueryLog.action == "image_generate", 1), else_=0)).label("image_logs"),
            func.sum(case((QueryLog.action == "photo_analysis", 1), else_=0)).label("photo_analysis_logs"),
            func.coalesce(func.sum(QueryLog.total_tokens), 0).label("total_tokens_logged"),
        )
        row = (await self.db.execute(query)).one()
        return {
            "total_logs": int(row.total_logs or 0),
            "ok_logs": int(row.ok_logs or 0),
            "error_logs": int(row.error_logs or 0),
            "image_logs": int(row.image_logs or 0),
            "photo_analysis_logs": int(row.photo_analysis_logs or 0),
            "total_tokens_logged": int(row.total_tokens_logged or 0),
        }
