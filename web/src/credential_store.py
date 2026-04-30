"""Web 全局默认 Credential 运行时存储."""

import secrets
import sqlite3
import threading
import time
from pathlib import Path

try:
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

from pydantic import ValidationError

from qqmusic_api import Credential

from .config import AccountConfig

ACCOUNT_CONFIG_FILE = "web/accounts.toml"


class CredentialStore:
    """SQLite Credential 运行时状态存储."""

    def __init__(self, path: str) -> None:
        """初始化 SQLite 存储路径."""
        self.path = Path(path)
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    def initialize(self) -> None:
        """初始化 SQLite 连接与表结构."""
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = self._connect()
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS credentials (
                  musicid INTEGER PRIMARY KEY,
                  credential_json TEXT NOT NULL,
                  updated_at INTEGER NOT NULL
                )
                """
            )
            connection.commit()

    def sync_accounts(self, accounts: list[AccountConfig]) -> None:
        """同步账号种子集合到运行时状态库."""
        with self._lock:
            connection = self._connect()
            valid_accounts = [account for account in accounts if account.has_login()]
            toml_ids = {account.musicid for account in valid_accounts}

            with connection:
                for account in valid_accounts:
                    exists = connection.execute(
                        "SELECT 1 FROM credentials WHERE musicid = ?",
                        (account.musicid,),
                    ).fetchone()
                    if exists is None:
                        self._upsert(account.to_credential())

                if toml_ids:
                    placeholders = ", ".join("?" for _ in toml_ids)
                    query = f"DELETE FROM credentials WHERE musicid NOT IN ({placeholders})"
                    connection.execute(query, tuple(toml_ids))
                else:
                    connection.execute("DELETE FROM credentials")

    def random_credentials(self) -> list[Credential]:
        """随机顺序返回全部可用 Credential."""
        with self._lock:
            rows = self._connect().execute("SELECT credential_json FROM credentials").fetchall()
        credentials: list[Credential] = []
        for row in rows:
            credential = _load_credential(row[0])
            if credential is not None and _credential_has_login(credential):
                credentials.append(credential)
        return _shuffled(credentials)

    def get(self, musicid: int) -> Credential | None:
        """按 musicid 返回当前 Credential."""
        with self._lock:
            row = (
                self._connect()
                .execute(
                    "SELECT credential_json FROM credentials WHERE musicid = ?",
                    (musicid,),
                )
                .fetchone()
            )
        if row is None:
            return None
        credential = _load_credential(row[0])
        if credential is None or not _credential_has_login(credential):
            return None
        return credential

    def update(self, credential: Credential) -> None:
        """保存刷新后的 Credential."""
        if not _credential_has_login(credential):
            raise ValueError("Credential 缺少 musicid 或 musickey")
        with self._lock:
            connection = self._connect()
            with connection:
                self._upsert(credential)

    def close(self) -> None:
        """关闭 SQLite 连接."""
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def _connect(self) -> sqlite3.Connection:
        """返回 SQLite 连接."""
        if self._connection is None:
            self._connection = sqlite3.connect(self.path, check_same_thread=False)
        return self._connection

    def _upsert(self, credential: Credential) -> None:
        """写入或替换单个 Credential."""
        self._connect().execute(
            """
            INSERT INTO credentials (musicid, credential_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(musicid) DO UPDATE SET
              credential_json = excluded.credential_json,
              updated_at = excluded.updated_at
            """,
            (
                credential.musicid,
                credential.model_dump_json(by_alias=True),
                int(time.time()),
            ),
        )


def load_account_configs(path: str) -> list[AccountConfig]:
    """从账号种子 TOML 文件读取账号配置."""
    account_file = Path(path)
    if not account_file.exists():
        return []
    with account_file.open("rb") as file:
        data = tomllib.load(file)
    account_items = data.get("account", [])
    if not isinstance(account_items, list):
        raise TypeError("账号种子文件必须使用 [[account]] 数组")
    try:
        return [AccountConfig.model_validate(item) for item in account_items]
    except ValidationError as exc:
        raise ValueError("账号种子文件格式无效") from exc


def credential_needs_refresh(credential: Credential) -> bool:
    """判断 Credential 是否需要本地刷新."""
    if credential.musickey_create_time <= 0 or credential.key_expires_in <= 0:
        return False
    return credential.is_expired()


def _credential_has_login(credential: Credential) -> bool:
    return credential.musicid > 0 and bool(credential.musickey)


def _load_credential(value: str) -> Credential | None:
    try:
        return Credential.model_validate_json(value)
    except ValueError:
        return None


def _shuffled(credentials: list[Credential]) -> list[Credential]:
    remaining = list(credentials)
    shuffled: list[Credential] = []
    while remaining:
        selected = secrets.choice(remaining)
        remaining.remove(selected)
        shuffled.append(selected)
    return shuffled
