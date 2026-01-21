from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # database_url: str
    db_host: str
    db_port: str
    db_name: str
    db_app_user: str
    db_app_pass: str
    mq_host: str
    mq_port: str
    mq_user: str
    mq_pass: str
    mq_exchange: str
    mq_queue_external_data: str


settings = Settings()  # pyright: ignore[reportCallIssue]
