from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_env: str = "dev"

    # Database
    database_url: str

    # Redis
    redis_url: str

    class Config:
        env_file = ".env"


settings = Settings()