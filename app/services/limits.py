from dataclasses import dataclass
from datetime import datetime

from app.core.plans import PLAN_MAP, PlanConfig
from app.models.user import User


@dataclass
class LimitPrecheckResult:
    allowed: bool
    reason: str | None = None
    daily_requests: int = 0
    max_output_tokens: int = 0
    used_bonus_credit: bool = False


def month_key_now() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def day_key_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def get_plan(user: User) -> PlanConfig:
    return PLAN_MAP.get(user.plan, PLAN_MAP["free"])


def reset_monthly_limits(user: User) -> None:
    user.month_key = month_key_now()
    user.monthly_requests_used = 0
    user.monthly_tokens_used = 0
    user.monthly_images_used = 0
    user.monthly_photo_analyses_used = 0
    user.monthly_long_texts_used = 0


def reset_daily_limits(user: User) -> None:
    user.day_key = day_key_now()
    user.daily_requests_used = 0
    user.daily_images_used = 0
    user.daily_photo_analyses_used = 0
    user.daily_long_texts_used = 0


def sync_month_if_needed(user: User) -> None:
    if user.month_key != month_key_now():
        reset_monthly_limits(user)


def sync_day_if_needed(user: User) -> None:
    if user.day_key != day_key_now():
        reset_daily_limits(user)


async def get_daily_usage(user: User) -> int:
    sync_day_if_needed(user)
    return user.daily_requests_used


async def get_daily_image_usage(user: User) -> int:
    sync_day_if_needed(user)
    return user.daily_images_used


async def get_daily_photo_analysis_usage(user: User) -> int:
    sync_day_if_needed(user)
    return user.daily_photo_analyses_used


async def get_daily_long_text_usage(user: User) -> int:
    sync_day_if_needed(user)
    return user.daily_long_texts_used


async def precheck_and_consume_request(user: User, estimated_input_tokens: int) -> LimitPrecheckResult:
    plan = get_plan(user)
    sync_month_if_needed(user)
    sync_day_if_needed(user)

    if user.monthly_requests_used >= plan.monthly_requests_limit:
        return LimitPrecheckResult(allowed=False, reason="monthly")

    remaining_monthly_tokens = plan.monthly_tokens_limit - user.monthly_tokens_used
    if remaining_monthly_tokens <= estimated_input_tokens:
        return LimitPrecheckResult(allowed=False, reason="monthly")

    dynamic_output_limit = min(plan.max_output_tokens, remaining_monthly_tokens - estimated_input_tokens)
    if dynamic_output_limit <= 0:
        return LimitPrecheckResult(allowed=False, reason="monthly")

    daily_after_increment = user.daily_requests_used + 1
    if daily_after_increment > plan.daily_requests_limit:
        return LimitPrecheckResult(allowed=False, reason="daily", daily_requests=daily_after_increment)

    user.daily_requests_used = daily_after_increment
    user.monthly_requests_used += 1
    return LimitPrecheckResult(
        allowed=True,
        daily_requests=daily_after_increment,
        max_output_tokens=dynamic_output_limit,
    )


async def precheck_and_consume_long_text_request(user: User) -> LimitPrecheckResult:
    plan = get_plan(user)
    sync_month_if_needed(user)
    sync_day_if_needed(user)

    if plan.monthly_long_text_limit <= 0 or plan.daily_long_text_limit <= 0:
        return LimitPrecheckResult(allowed=False, reason="long_text_plan")

    if user.monthly_long_texts_used >= plan.monthly_long_text_limit:
        return LimitPrecheckResult(allowed=False, reason="long_text_monthly")

    daily_after_increment = user.daily_long_texts_used + 1
    if daily_after_increment > plan.daily_long_text_limit:
        return LimitPrecheckResult(allowed=False, reason="long_text_daily", daily_requests=daily_after_increment)

    user.daily_long_texts_used = daily_after_increment
    user.monthly_long_texts_used += 1
    return LimitPrecheckResult(allowed=True, daily_requests=daily_after_increment)


async def precheck_and_consume_image_request(user: User) -> LimitPrecheckResult:
    plan = get_plan(user)
    sync_month_if_needed(user)
    sync_day_if_needed(user)

    use_bonus_credit = False
    if plan.monthly_images_limit <= 0:
        if user.bonus_image_credits <= 0:
            return LimitPrecheckResult(allowed=False, reason="image_plan")
        use_bonus_credit = True
    elif user.monthly_images_used >= plan.monthly_images_limit:
        if user.bonus_image_credits <= 0:
            return LimitPrecheckResult(allowed=False, reason="image_monthly")
        use_bonus_credit = True

    effective_daily_limit = plan.daily_images_limit if plan.daily_images_limit > 0 else 1
    daily_after_increment = user.daily_images_used + 1
    if daily_after_increment > effective_daily_limit:
        return LimitPrecheckResult(allowed=False, reason="image_daily", daily_requests=daily_after_increment)

    user.daily_images_used = daily_after_increment
    if use_bonus_credit:
        user.bonus_image_credits = max(0, user.bonus_image_credits - 1)
    else:
        user.monthly_images_used += 1

    return LimitPrecheckResult(allowed=True, daily_requests=daily_after_increment, used_bonus_credit=use_bonus_credit)


async def precheck_and_consume_photo_analysis_request(user: User) -> LimitPrecheckResult:
    plan = get_plan(user)
    sync_month_if_needed(user)
    sync_day_if_needed(user)

    if user.monthly_photo_analyses_used >= plan.monthly_photo_analysis_limit:
        return LimitPrecheckResult(allowed=False, reason="photo_monthly")

    daily_after_increment = user.daily_photo_analyses_used + 1
    if daily_after_increment > plan.daily_photo_analysis_limit:
        return LimitPrecheckResult(allowed=False, reason="photo_daily", daily_requests=daily_after_increment)

    user.daily_photo_analyses_used = daily_after_increment
    user.monthly_photo_analyses_used += 1
    return LimitPrecheckResult(allowed=True, daily_requests=daily_after_increment)


def consume_monthly_tokens(user: User, total_tokens: int) -> None:
    sync_month_if_needed(user)
    user.monthly_tokens_used += max(0, total_tokens)


async def rollback_request(user: User) -> None:
    sync_day_if_needed(user)
    user.daily_requests_used = max(0, user.daily_requests_used - 1)
    user.monthly_requests_used = max(0, user.monthly_requests_used - 1)


async def rollback_long_text_request(user: User) -> None:
    sync_day_if_needed(user)
    user.daily_long_texts_used = max(0, user.daily_long_texts_used - 1)
    user.monthly_long_texts_used = max(0, user.monthly_long_texts_used - 1)


async def rollback_image_request(user: User, used_bonus_credit: bool = False) -> None:
    sync_day_if_needed(user)
    user.daily_images_used = max(0, user.daily_images_used - 1)
    if used_bonus_credit:
        user.bonus_image_credits += 1
    else:
        user.monthly_images_used = max(0, user.monthly_images_used - 1)


async def rollback_photo_analysis_request(user: User) -> None:
    sync_day_if_needed(user)
    user.daily_photo_analyses_used = max(0, user.daily_photo_analyses_used - 1)
    user.monthly_photo_analyses_used = max(0, user.monthly_photo_analyses_used - 1)
