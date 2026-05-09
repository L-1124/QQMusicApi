"""Web 层配置管理."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource

from qqmusic_api import Credential


class LogConfig(BaseModel):
    """日志配置."""

    mode: Annotated[Literal["console", "file", "both"], Field(description="日志模式: console/file/both")] = "console"
    level: Annotated[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], Field(description="日志级别")] = "INFO"
    file_path: str = Field(default="web/data/logs/app.log", description="日志文件路径 (当 mode 为 file 或 both 时使用)")
    console_format: str = Field(
        default="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan> | <level>{message}</level>",
        description="控制台日志格式",
    )
    file_format: str = Field(
        default="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name} | {message}",
        description="文件日志格式",
    )
    max_bytes: int = Field(default=10485760, ge=1, description="单个日志文件最大字节数 (10MB)")
    backup_count: int = Field(default=5, ge=0, description="保留的备份日志文件数")


class ServerConfig(BaseModel):
    """服务器配置."""

    host: str = Field(default="127.0.0.1", description="绑定地址")
    port: int = Field(default=8080, description="监听端口")
    workers: int = Field(default=1, description="工作进程数")
    limit_concurrency: int | None = Field(default=None, ge=1, description="Uvicorn 最大并发连接/任务数")


class CacheConfig(BaseModel):
    """缓存配置."""

    ttl: int = Field(default=60, description="默认缓存过期时间(秒)")
    memory_max_size: int = Field(default=1024, description="内存缓存最大条目数")
    backend: Literal["memory", "redis"] = Field(default="memory", description="缓存后端 (memory/redis)")
    redis_url: str | None = Field(default=None, description="Redis 连接地址")
    redis_prefix: str = Field(default="qqapi:", description="Redis 键前缀")


class SecurityConfig(BaseModel):
    """安全与限流配置."""

    enabled: bool = Field(default=True, description="是否启用访问控制与限流")
    ip_list_mode: Literal["allowlist", "denylist"] = Field(default="denylist", description="IP 名单模式")
    ip_allowlist: list[str] = Field(default_factory=list, description="白名单 IP 或 CIDR")
    ip_denylist: list[str] = Field(default_factory=list, description="黑名单 IP 或 CIDR")
    trusted_proxy_ips: list[str] = Field(default_factory=list, description="可信代理 IP 或 CIDR")
    client_ip_header: str | None = Field(default=None, description="可信代理提供的客户端 IP 头")
    rate_limit_enabled: bool = Field(default=True, description="是否启用 IP 限流")
    rate_limit_capacity: int = Field(default=60, ge=1, description="单窗口最大请求数")
    rate_limit_window_seconds: int = Field(default=60, ge=1, description="限流窗口秒数")
    rate_limit_exempt_ips: list[str] = Field(default_factory=list, description="限流豁免 IP 或 CIDR")
    concurrency_limit_enabled: bool = Field(default=True, description="是否启用全局并发限制")
    concurrency_limit: int = Field(default=100, ge=1, description="单进程最大并发业务请求数")
    concurrency_retry_after_seconds: int = Field(default=1, ge=1, description="并发过载重试等待秒数")
    cors_enabled: bool = Field(default=False, description="是否启用 CORS")
    cors_allow_origins: list[str] = Field(default_factory=list, description="允许跨域访问的 Origin 列表")
    cors_allow_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "OPTIONS"],
        description="允许跨域访问的方法",
    )
    cors_allow_headers: list[str] = Field(
        default_factory=lambda: ["Accept", "Accept-Language", "Content-Language", "Content-Type"],
        description="允许跨域访问的请求头",
    )
    cors_allow_credentials: bool = Field(default=True, description="是否允许跨域凭据")
    cors_max_age: int = Field(default=600, ge=0, description="CORS 预检缓存秒数")


class CredentialStoreConfig(BaseModel):
    """全局默认账号运行时状态存储配置."""

    backend: Literal["sqlite"] = Field(default="sqlite", description="运行时 Credential 存储后端, 可选值: sqlite")
    path: str = Field(default="web/data/credentials.sqlite3", description="SQLite Credential 状态库路径")


class CredentialConfig(BaseModel):
    """全局默认凭证配置."""

    enabled: bool = Field(default=False, description="是否启用全局默认登录凭证")
    api: dict[str, list[str]] = Field(
        default_factory=lambda: {"song": ["get_song_urls", "get_song_url"]},
        description="允许使用全局默认登录凭证的 API 映射",
    )
    store: CredentialStoreConfig = CredentialStoreConfig()

    def api_enabled(self, api_key: str) -> bool:
        """判断指定 API 是否允许使用全局默认登录凭证."""
        if not self.enabled:
            return False
        module, separator, method = api_key.partition(".")
        if not separator:
            return False
        methods = self.api.get(module)
        if methods is None:
            return False
        return not methods or method in methods


class AccountConfig(BaseModel):
    """账号凭证种子配置."""

    musicid: int = Field(default=0, ge=0)
    musickey: str = ""
    openid: str = ""
    refresh_token: str = ""
    access_token: str = ""
    expired_at: int = Field(default=0, ge=0)
    unionid: str = ""
    str_musicid: str = ""
    refresh_key: str = ""
    musickey_create_time: int = Field(default=0, ge=0)
    key_expires_in: int = Field(default=0, ge=0)
    first_login: int = Field(default=0, ge=0)
    bind_account_type: int = Field(default=0, ge=0)
    need_refresh_key_in: int = Field(default=0, ge=0)
    encrypt_uin: str = ""
    login_type: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _load_credential_json(cls, data: Any) -> Any:
        """允许账号条目直接提供 Credential JSON."""
        if not isinstance(data, dict):
            return data
        raw_credential = data.get("credential") or data.get("credential_json")
        if raw_credential is None:
            return data
        credential = (
            Credential.model_validate_json(raw_credential)
            if isinstance(raw_credential, str)
            else Credential.model_validate(raw_credential)
        )
        merged = credential.model_dump()
        merged.update({key: value for key, value in data.items() if key not in {"credential", "credential_json"}})
        return merged

    def has_login(self) -> bool:
        """判断是否包含可用登录凭证."""
        return self.musicid > 0 and bool(self.musickey)

    def to_credential(self) -> Credential:
        """转换为运行时 Credential."""
        data: dict[str, Any] = {
            "musicid": self.musicid,
            "musickey": self.musickey,
            "openid": self.openid,
            "refresh_token": self.refresh_token,
            "access_token": self.access_token,
            "expired_at": self.expired_at,
            "unionid": self.unionid,
            "str_musicid": self.str_musicid or str(self.musicid),
            "refresh_key": self.refresh_key,
            "musickey_create_time": self.musickey_create_time,
            "key_expires_in": self.key_expires_in,
            "first_login": self.first_login,
            "bind_account_type": self.bind_account_type,
            "need_refresh_key_in": self.need_refresh_key_in,
            "encrypt_uin": self.encrypt_uin,
        }
        if self.login_type > 0:
            data["login_type"] = self.login_type
        return Credential.model_validate(data)


class Settings(BaseSettings):
    """Web 服务全局配置."""

    model_config = SettingsConfigDict(
        env_prefix="QQMUSIC_",
        env_file=".env",
        toml_file="web/config.toml",
        extra="ignore",
    )

    logging: LogConfig = LogConfig()
    server: ServerConfig = ServerConfig()
    cache: CacheConfig = CacheConfig()
    security: SecurityConfig = SecurityConfig()
    credential: CredentialConfig = CredentialConfig()

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
