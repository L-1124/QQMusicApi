"""Web 全局默认 Credential 运行时存储."""

import logging
import secrets
import sqlite3
import threading
import time
from contextlib import suppress
from pathlib import Path

try:
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib

from pydantic import ValidationError

from qqmusic_api import Credential

from .config import AccountConfig

logger = logging.getLogger(__name__)

ACCOUNT_CONFIG_FILE = "web/accounts.toml"


class CredentialStore:
    """SQLite 凭证运行时状态存储."""

    def __init__(self, path: str) -> None:
        """初始化存储路径."""
        self.path = Path(path)
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    def initialize(self) -> None:
        """初始化 SQLite 连接与表结构."""
        with self._lock:
            logger.info(f"初始化凭证存储: {self.path}")
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
            with suppress(sqlite3.OperationalError):
                connection.execute("ALTER TABLE credentials ADD COLUMN valid INTEGER DEFAULT 1")
            connection.commit()
            logger.debug("凭证存储表结构初始化完成")

    def sync_accounts(self, accounts: list[AccountConfig]) -> None:
        """同步账号种子到状态库."""
        with self._lock:
            connection = self._connect()
            valid_accounts = [account for account in accounts if account.has_login()]
            toml_ids = {account.musicid for account in valid_accounts}

            logger.info(f"同步账号种子: 总计 {len(valid_accounts)} 个有效账号")

            with connection:
                for account in valid_accounts:
                    exists = connection.execute(
                        "SELECT 1 FROM credentials WHERE musicid = ?",
                        (account.musicid,),
                    ).fetchone()
                    if exists is None:
                        logger.debug(f"新增账号种子: musicid {account.musicid}")
                        self._upsert(account.to_credential())
                    else:
                        logger.debug(f"账号种子已存在, 跳过: musicid {account.musicid}")

                if toml_ids:
                    placeholders = ", ".join("?" for _ in toml_ids)
                    query = f"DELETE FROM credentials WHERE musicid NOT IN ({placeholders})"
                    cursor = connection.execute(query, tuple(toml_ids))
                    deleted = cursor.rowcount
                    if deleted > 0:
                        logger.info(f"删除不在种子中的账号: {deleted} 个")
                else:
                    connection.execute("DELETE FROM credentials")
                    logger.warning("删除所有账号: 未配置有效的账号种子")

            logger.info("账号种子同步完成")

    def random_credentials(self) -> list[Credential]:
        """随机顺序返回全部有效 Credential."""
        with self._lock:
            rows = self._connect().execute("SELECT credential_json FROM credentials WHERE valid = 1").fetchall()
        credentials: list[Credential] = []
        for row in rows:
            credential = _load_credential(row[0])
            if credential is not None and credential_has_login(credential):
                credentials.append(credential)
        logger.debug(f"获取有效凭证: {len(credentials)} 个")
        rng = secrets.SystemRandom()
        rng.shuffle(credentials)
        return credentials

    def get(self, musicid: int) -> Credential | None:
        """按 musicid 获取凭证."""
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
            logger.debug(f"凭证不存在: musicid {musicid}")
            return None
        credential = _load_credential(row[0])
        if credential is None or not credential_has_login(credential):
            logger.debug(f"凭证无效或缺少登录信息: musicid {musicid}")
            return None
        logger.debug(f"凭证获取成功: musicid {musicid}")
        return credential

    def update(self, credential: Credential) -> None:
        """保存刷新后的 Credential 并标记为有效."""
        if not credential_has_login(credential):
            raise ValueError("Credential 缺少 musicid 或 musickey")
        logger.debug(f"更新凭证: musicid {credential.musicid}")
        with self._lock:
            connection = self._connect()
            with connection:
                self._upsert(credential)
                connection.execute(
                    "UPDATE credentials SET valid = 1 WHERE musicid = ?",
                    (credential.musicid,),
                )
        logger.info(f"凭证已更新并标记为有效: musicid {credential.musicid}")

    def mark_invalid(self, musicid: int) -> None:
        """标记账号为无效."""
        logger.warning(f"标记凭证为无效: musicid {musicid}")
        with self._lock:
            connection = self._connect()
            connection.execute(
                "UPDATE credentials SET valid = 0 WHERE musicid = ?",
                (musicid,),
            )
            connection.commit()

    def get_all_musicids(self) -> list[int]:
        """返回全部已知 musicid."""
        with self._lock:
            rows = self._connect().execute("SELECT musicid FROM credentials").fetchall()
        musicids = [row[0] for row in rows]
        logger.debug(f"获取所有 musicid: {len(musicids)} 个")
        return musicids

    def close(self) -> None:
        """关闭 SQLite 连接."""
        with self._lock:
            if self._connection is not None:
                logger.debug(f"关闭凭证存储连接: {self.path}")
                self._connection.close()
                self._connection = None

    def _connect(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(self.path, check_same_thread=False)
        return self._connection

    def _upsert(self, credential: Credential) -> None:
        """写入或替换单个 Credential."""
        logger.debug(f"保存凭证到存储: musicid {credential.musicid}")
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
        logger.debug(f"账号种子文件不存在: {path}")
        return []
    logger.info(f"读取账号种子文件: {path}")
    with account_file.open("rb") as file:
        data = tomllib.load(file)
    account_items = data.get("account", [])
    if not isinstance(account_items, list):
        logger.error("账号种子文件格式错误: account 必须是数组")
        raise TypeError("账号种子文件必须使用 [[account]] 数组") from None
    try:
        configs = [AccountConfig.model_validate(item) for item in account_items]
        logger.info(f"账号种子加载成功: {len(configs)} 个配置")
        return configs
    except ValidationError as exc:
        logger.exception("账号种子文件校验失败")
        raise ValueError("账号种子文件格式无效") from exc


def credential_needs_refresh(credential: Credential) -> bool:
    """判断凭证是否需要刷新."""
    if credential.musickey_create_time <= 0 or credential.key_expires_in <= 0:
        return False
    needs_refresh = credential.is_expired()
    if needs_refresh:
        logger.debug(
            f"凭证需要刷新 (检查 musicid {credential.musicid}): 创建于 {credential.musickey_create_time}, 有效期 {credential.key_expires_in}s"
        )
    return needs_refresh


def credential_has_login(credential: Credential) -> bool:
    """判断 Credential 是否包含可用登录凭证."""
    return credential.musicid > 0 and bool(credential.musickey)


def _load_credential(value: str) -> Credential | None:
    try:
        return Credential.model_validate_json(value)
    except ValueError:
        return None
