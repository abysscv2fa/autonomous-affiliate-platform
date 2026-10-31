from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./affiliate.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_image_model: str = "gpt-image-1"
    openai_image_quality: str = "low"
    autopilot_token: str = ""
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    metricool_user_token: str = ""
    metricool_user_id: str = "6076356"
    metricool_blog_id: str = "7771372"
    metricool_timezone: str = "Asia/Ho_Chi_Minh"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
