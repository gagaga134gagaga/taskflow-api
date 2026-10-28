from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./taskflow.db"
    rabbitmq_url: str = "amqp://guest:guest@localhost/"
    api_key: str = "local-development-key"
    max_attempts: int = 3
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
