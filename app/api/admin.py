from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.repositories.query_log_repo import QueryLogRepository
from app.repositories.user_repo import UserRepository
from app.services.google_sheets_sync import GoogleSheetsSyncService
from app.services.limits import reset_daily_limits, reset_monthly_limits

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


def _plan_price_usd(plan: str) -> int:
    normalized = "pro" if plan == "paid" else plan
    if normalized == "student":
        return settings.student_price_usd
    if normalized == "pro":
        return settings.pro_price_usd
    return 0


@router.get("/users", dependencies=[Depends(verify_admin_token)])
async def admin_list_users(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    plan: str | None = Query(default=None),
    is_banned: bool | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    users, total = await UserRepository(db).list_users(
        limit=limit,
        offset=offset,
        search=search,
        plan=plan,
        is_banned=is_banned,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return {
        "total": total,
        "items": [
            {
                "telegram_id": user.telegram_id,
                "username": user.username,
                "language": user.language,
                "plan": user.plan,
                "plan_price_usd": _plan_price_usd(user.plan),
                "is_banned": user.is_banned,
                "month_key": user.month_key,
                "monthly_requests_used": user.monthly_requests_used,
                "monthly_tokens_used": user.monthly_tokens_used,
                "monthly_images_used": user.monthly_images_used,
                "monthly_photo_analyses_used": user.monthly_photo_analyses_used,
                "monthly_long_texts_used": user.monthly_long_texts_used,
                "bonus_image_credits": user.bonus_image_credits,
                "created_at": user.created_at,
            }
            for user in users
        ]
    }


@router.get("/query-logs", dependencies=[Depends(verify_admin_token)])
async def admin_list_query_logs(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    telegram_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    logs = await QueryLogRepository(db).list_logs(limit=limit, offset=offset, telegram_id=telegram_id)
    return {
        "items": [
            {
                "id": item.id,
                "telegram_id": item.telegram_id,
                "action": item.action,
                "plan": item.plan,
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "total_tokens": item.total_tokens,
                "status": item.status,
                "error_message": item.error_message,
                "created_at": item.created_at,
            }
            for item in logs
        ]
    }


@router.get("/stats", dependencies=[Depends(verify_admin_token)])
async def admin_stats(db: AsyncSession = Depends(get_db)) -> dict:
    user_stats = await UserRepository(db).get_stats()
    log_stats = await QueryLogRepository(db).get_stats()
    return {"users": user_stats, "logs": log_stats}


@router.post("/users/{telegram_id}/ban", dependencies=[Depends(verify_admin_token)])
async def admin_ban_user(telegram_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    repo = UserRepository(db)
    user = await repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_banned = True
    await repo.save(user)
    await db.commit()
    return {"ok": True}


@router.post("/users/{telegram_id}/unban", dependencies=[Depends(verify_admin_token)])
async def admin_unban_user(telegram_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    repo = UserRepository(db)
    user = await repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_banned = False
    await repo.save(user)
    await db.commit()
    return {"ok": True}


@router.post("/users/{telegram_id}/plan/{plan}", dependencies=[Depends(verify_admin_token)])
async def admin_change_plan(telegram_id: int, plan: str, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    if plan not in {"free", "student", "pro", "paid"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan must be free, student, or pro")
    if plan == "paid":
        plan = "pro"

    repo = UserRepository(db)
    user = await repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.plan = plan
    await repo.save(user)
    await db.commit()
    return {"ok": True}


@router.post("/users/{telegram_id}/reset-limits", dependencies=[Depends(verify_admin_token)])
async def admin_reset_limits(
    telegram_id: int,
    scope: Literal["daily", "monthly", "all"] = Query(default="all"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    repo = UserRepository(db)
    user = await repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if scope in {"daily", "all"}:
        reset_daily_limits(user)

    if scope in {"monthly", "all"}:
        reset_monthly_limits(user)
        await repo.save(user)

    await db.commit()
    return {
        "ok": True,
        "scope": scope,
        "telegram_id": user.telegram_id,
        "monthly_requests_used": user.monthly_requests_used,
        "monthly_tokens_used": user.monthly_tokens_used,
        "monthly_images_used": user.monthly_images_used,
        "monthly_photo_analyses_used": user.monthly_photo_analyses_used,
        "monthly_long_texts_used": user.monthly_long_texts_used,
    }


@router.post("/users/{telegram_id}/grant-image-credits", dependencies=[Depends(verify_admin_token)])
async def admin_grant_image_credits(
    telegram_id: int,
    amount: int = Query(..., ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    repo = UserRepository(db)
    user = await repo.get_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.bonus_image_credits += amount
    await repo.save(user)
    await db.commit()

    return {
        "ok": True,
        "telegram_id": user.telegram_id,
        "amount_added": amount,
        "bonus_image_credits": user.bonus_image_credits,
    }


@router.post("/sync/google-sheets", dependencies=[Depends(verify_admin_token)])
async def admin_google_sheets_sync(
    direction: Literal["push", "pull", "both"] = Query(default="both"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = GoogleSheetsSyncService(db)
    try:
        if direction == "push":
            result = await service.push_to_sheets()
        elif direction == "pull":
            result = await service.pull_from_sheets()
        else:
            result = await service.sync_both()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "ok": True,
        "direction": direction,
        "pulled_updated": result.pulled_updated,
        "pulled_created": result.pulled_created,
        "pushed_rows": result.pushed_rows,
    }
