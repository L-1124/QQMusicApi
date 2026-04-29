"""Web 层配置管理."""

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource


class ServerConfig(BaseModel):
    """Server 模块配置."""

    host: str = Field(default="127.0.0.1", description="绑定地址")
    port: int = Field(default=8080, description="监听端口")
    workers: int = Field(default=1, description="工作进程数")


class CacheConfig(BaseModel):
    """Cache 模块配置."""

    ttl: int = Field(default=60, description="默认缓存过期时间(秒)")
    memory_max_size: int = Field(default=1024, description="内存缓存最大条目数")
    backend: Literal["memory", "redis"] = Field(default="memory", description="缓存后端 (memory/redis)")
    redis_url: str | None = Field(default=None, description="Redis 连接地址")
    redis_prefix: str = Field(default="qqapi:", description="Redis 键前缀")


class Settings(BaseSettings):
    """Web 服务全局配置项."""

    model_config = SettingsConfigDict(
        env_prefix="QQMUSIC_",
        env_file=".env",
        toml_file="web/config.toml",
        extra="ignore",
    )

    server: ServerConfig = ServerConfig()
    cache: CacheConfig = CacheConfig()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """配置加载优先级: Init > Env > Dotenv > Toml > Defaults."""
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


settings = Settings()
