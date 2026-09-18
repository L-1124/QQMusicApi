"""进程内请求合并: 同一缓存键的并发请求只回源一次.

Note:
    合并只用在持有缓存策略的读路由上. 等待者复用 leader 的结果或失败标记, 等待超时时
    返回默认错误而不是自行回源, 避免上游故障期间把并发等待者变成并发风暴.
"""

import logging
from asyncio import Event
from dataclasses import dataclass, field
from typing import Any

from anyio import move_on_after

logger = logging.getLogger(__name__)


@dataclass
class Flight:
    """同一缓存键在途请求的协调状态.

    Note:
        `payload` 存 leader 的原始载荷而不是构造好的响应: 响应的 ETag 与 304 判定依赖
        调用方自己的 `If-None-Match`, 共享响应会把 leader 的 304 空响应发给其他调用方.
    """

    event: Event = field(default_factory=Event)
    payload: Any = None
    error: BaseException | None = None


class Coalescer:
    """进程内请求合并器: 按键注册表 + 双重检查锁定."""

    def __init__(self, wait_timeout: float = 2.0) -> None:
        """按等待上限初始化合并器.

        Args:
            wait_timeout: 等待者等待 leader 的上限秒数; 非正数表示等待立即超时, 即等待者
                一律降级返回而不复用 leader 结果.
        """
        self._wait_timeout = wait_timeout
        self._flights: dict[str, Flight] = {}

    @property
    def wait_timeout(self) -> float:
        """返回等待 leader 的上限秒数."""
        return self._wait_timeout

    @property
    def in_flight(self) -> int:
        """返回当前在途组数量, 用于观测注册表是否泄漏."""
        return len(self._flights)

    def enter(self, key: str) -> tuple[Flight, bool]:
        """同步原子地加入或创建在途组.

        Note:
            必须是同步函数: 「查注册表 + 创建在途组」之间不能有 await, 否则同一时刻可能
            产生两个 leader.

        Returns:
            (在途组, 是否为 leader).
        """
        flight = self._flights.get(key)
        if flight is not None:
            logger.debug("请求合并: 加入在途组 %s", key)
            return flight, False
        flight = Flight()
        self._flights[key] = flight
        logger.debug("请求合并: 成为 leader 回源 %s", key)
        return flight, True

    def leave(self, key: str) -> None:
        """注销在途组并唤醒等待者.

        Note:
            注销与置位 event 在一次同步调用内完成, 否则等待者可能看到注册表已清空、
            event 尚未置位的中间态.
        """
        flight = self._flights.pop(key, None)
        if flight is None:
            return
        flight.event.set()

    async def wait(self, flight: Flight) -> bool:
        """等待 leader 完成.

        Returns:
            是否等待超时. 超时时调用方必须降级返回, 不得自行回源.
        """
        timeout = self._wait_timeout
        if timeout <= 0:
            return True
        with move_on_after(timeout) as scope:
            await flight.event.wait()
        if scope.cancelled_caught:
            logger.warning("请求合并: 等待 leader 超过 %.1fs, 降级返回默认错误", timeout)
            return True
        return False
