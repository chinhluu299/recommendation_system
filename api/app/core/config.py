from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Ecommerce Recommendation API"
    app_env: str = "dev"
    app_port: int = 8000

    database_url: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120

    core_service_url: str = "http://localhost:9000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
