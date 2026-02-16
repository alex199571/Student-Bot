from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Telegram AI Student Bot"
    app_env: str = "local"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str
    redis_url: str = ""

    telegram_bot_token: str
    telegram_webhook_secret: str
    telegram_webhook_url: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_image_model: str = "gpt-image-1"
    student_price_usd: int = 9
    pro_price_usd: int = 19
    google_sheets_id: str = ""
    google_sheets_worksheet: str = "users"
    google_service_account_file: str = "credentials/google-service-account.json"

    admin_token: str
    default_timezone: str = "Europe/Kyiv"

    model_config = SettingsConfigDict(env_file="token.env", env_file_encoding="utf-8", case_sensitive=False)


settings = Settings()
