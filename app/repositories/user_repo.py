from sqlalchemy import String, asc, case, cast, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        query = select(User).where(User.telegram_id == telegram_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        language: str,
        month_key: str,
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return user

        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            language=language,
            month_key=month_key,
            plan="free",
        )
        self.db.add(user)
        await self.db.flush()
        return user

    def _build_filters(
        self,
        search: str | None = None,
        plan: str | None = None,
        is_banned: bool | None = None,
    ) -> list:
        conditions = []

        if plan:
            if plan == "paid":
                plan = "pro"
            conditions.append(User.plan == plan)

        if is_banned is not None:
            conditions.append(User.is_banned.is_(is_banned))

        if search:
            like_any = f"%{search}%"
            conditions.append(
                or_(
                    cast(User.telegram_id, String).ilike(like_any),
                    func.coalesce(User.username, "").ilike(like_any),
                    func.coalesce(User.first_name, "").ilike(like_any),
                    func.coalesce(User.language, "").ilike(like_any),
                    func.coalesce(User.plan, "").ilike(like_any),
                )
            )

        return conditions

    async def list_users(
        self,
        limit: int,
        offset: int,
        search: str | None = None,
        plan: str | None = None,
        is_banned: bool | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[User], int]:
        conditions = self._build_filters(search=search, plan=plan, is_banned=is_banned)

        sort_map = {
            "telegram_id": User.telegram_id,
            "username": User.username,
            "language": User.language,
            "plan": User.plan,
            "is_banned": User.is_banned,
            "month_key": User.month_key,
            "monthly_requests_used": User.monthly_requests_used,
            "monthly_tokens_used": User.monthly_tokens_used,
            "monthly_images_used": User.monthly_images_used,
            "monthly_photo_analyses_used": User.monthly_photo_analyses_used,
            "monthly_long_texts_used": User.monthly_long_texts_used,
            "bonus_image_credits": User.bonus_image_credits,
            "created_at": User.created_at,
        }
        sort_column = sort_map.get(sort_by, User.created_at)
        order_clause = asc(sort_column) if sort_order == "asc" else desc(sort_column)

        query = select(User).where(*conditions).order_by(order_clause).limit(limit).offset(offset)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        count_query = select(func.count(User.id)).where(*conditions)
        total = int((await self.db.execute(count_query)).scalar() or 0)
        return items, total

    async def save(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        return user

    async def list_all_users(self) -> list[User]:
        query = select(User).order_by(User.id.asc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_stats(self) -> dict[str, int]:
        query = select(
            func.count(User.id).label("total_users"),
            func.sum(case((User.plan == "student", 1), else_=0)).label("student_users"),
            func.sum(case((User.plan == "pro", 1), else_=0)).label("pro_users"),
            func.sum(case((User.plan == "paid", 1), else_=0)).label("legacy_paid_users"),
            func.sum(case((User.plan == "free", 1), else_=0)).label("free_users"),
            func.sum(case((User.is_banned.is_(True), 1), else_=0)).label("banned_users"),
            func.coalesce(func.sum(User.monthly_requests_used), 0).label("monthly_requests_used"),
            func.coalesce(func.sum(User.monthly_tokens_used), 0).label("monthly_tokens_used"),
            func.coalesce(func.sum(User.monthly_images_used), 0).label("monthly_images_used"),
            func.coalesce(func.sum(User.monthly_photo_analyses_used), 0).label("monthly_photo_analyses_used"),
            func.coalesce(func.sum(User.monthly_long_texts_used), 0).label("monthly_long_texts_used"),
            func.coalesce(func.sum(User.bonus_image_credits), 0).label("bonus_image_credits"),
        )
        row = (await self.db.execute(query)).one()
        return {
            "total_users": int(row.total_users or 0),
            "student_users": int(row.student_users or 0),
            "pro_users": int((row.pro_users or 0) + (row.legacy_paid_users or 0)),
            "free_users": int(row.free_users or 0),
            "banned_users": int(row.banned_users or 0),
            "monthly_requests_used": int(row.monthly_requests_used or 0),
            "monthly_tokens_used": int(row.monthly_tokens_used or 0),
            "monthly_images_used": int(row.monthly_images_used or 0),
            "monthly_photo_analyses_used": int(row.monthly_photo_analyses_used or 0),
            "monthly_long_texts_used": int(row.monthly_long_texts_used or 0),
            "bonus_image_credits": int(row.bonus_image_credits or 0),
        }
