from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    flask_secret_key: str = Field(default="change-this-secret", validation_alias="FLASK_SECRET_KEY")
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    mysql_host: str = Field(default="127.0.0.1", validation_alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, validation_alias="MYSQL_PORT")
    mysql_user: str = Field(default="root", validation_alias="MYSQL_USER")
    mysql_password: str = Field(default="", validation_alias="MYSQL_PASSWORD")
    mysql_db: str = Field(default="otaku_tracker", validation_alias="MYSQL_DB")

    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url

        encoded_user = quote_plus(self.mysql_user)
        encoded_password = quote_plus(self.mysql_password)
        return (
            "mysql+pymysql://"
            f"{encoded_user}:{encoded_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
            "?charset=utf8mb4"
        )
