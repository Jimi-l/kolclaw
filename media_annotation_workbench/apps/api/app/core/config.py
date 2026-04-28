from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


Role = Literal["admin", "annotator", "viewer"]


class LocalUserConfig(BaseModel):
    username: str
    password: str
    display_name: str
    role: Role


class Settings(BaseSettings):
    api_title: str = "Media Annotation Workbench API"
    database_url: str = "postgresql+psycopg://media_workbench:media_workbench@127.0.0.1:5432/media_annotation_workbench"
    secret_key: str = "change-this-secret-for-production"
    access_token_ttl_seconds: int = 86400
    api_cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    default_snapshot_dir: str = "/home/tuo/project/media_knowledge_factory/outputs/seed_v1"
    local_users: list[LocalUserConfig] = Field(
        default_factory=lambda: [
            LocalUserConfig(
                username="admin",
                password="admin123",
                display_name="系统管理员",
                role="admin",
            ),
            LocalUserConfig(
                username="annotator",
                password="annotator123",
                display_name="业务标注员",
                role="annotator",
            ),
            LocalUserConfig(
                username="viewer",
                password="viewer123",
                display_name="只读访客",
                role="viewer",
            ),
        ]
    )

    model_config = SettingsConfigDict(
        env_prefix="WORKBENCH_",
        env_nested_delimiter="__",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
