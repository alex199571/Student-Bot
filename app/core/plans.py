from dataclasses import dataclass


@dataclass(frozen=True)
class PlanConfig:
    name: str
    monthly_requests_limit: int
    daily_requests_limit: int
    monthly_tokens_limit: int
    max_output_tokens: int
    monthly_images_limit: int
    daily_images_limit: int
    monthly_photo_analysis_limit: int
    daily_photo_analysis_limit: int
    monthly_long_text_limit: int
    daily_long_text_limit: int


FREE_PLAN = PlanConfig(
    name="free",
    monthly_requests_limit=50,
    daily_requests_limit=5,
    monthly_tokens_limit=20_000,
    max_output_tokens=400,
    monthly_images_limit=0,
    daily_images_limit=0,
    monthly_photo_analysis_limit=8,
    daily_photo_analysis_limit=1,
    monthly_long_text_limit=0,
    daily_long_text_limit=0,
)

STUDENT_PLAN = PlanConfig(
    name="student",
    monthly_requests_limit=250,
    daily_requests_limit=25,
    monthly_tokens_limit=120_000,
    max_output_tokens=1_200,
    monthly_images_limit=0,
    daily_images_limit=0,
    monthly_photo_analysis_limit=60,
    daily_photo_analysis_limit=6,
    monthly_long_text_limit=40,
    daily_long_text_limit=4,
)

PRO_PLAN = PlanConfig(
    name="pro",
    monthly_requests_limit=1_000,
    daily_requests_limit=100,
    monthly_tokens_limit=300_000,
    max_output_tokens=2_400,
    monthly_images_limit=30,
    daily_images_limit=2,
    monthly_photo_analysis_limit=300,
    daily_photo_analysis_limit=30,
    monthly_long_text_limit=120,
    daily_long_text_limit=12,
)

PLAN_MAP = {
    "free": FREE_PLAN,
    "student": STUDENT_PLAN,
    "pro": PRO_PLAN,
    "paid": PRO_PLAN,  # backward compatibility for old data
}
