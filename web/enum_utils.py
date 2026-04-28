"""Web 层枚举查询参数辅助函数."""

from enum import Enum
from typing import Any


def iter_enum_members(target_type: type[Enum]) -> list[Enum]:
    """按目标枚举与子类枚举顺序返回成员."""
    members = list(target_type.__members__.values())
    for sub in target_type.__subclasses__():
        members.extend(sub.__members__.values())
    return members


def coerce_enum_value(value: Any, target_type: type[Enum]) -> Any:
    """将枚举名称或简单枚举值转换为枚举成员."""
    if isinstance(value, target_type):
        return value
    text = str(value)
    normalized = text.casefold()

    for member in iter_enum_members(target_type):
        if member.name.casefold() == normalized:
            return member
        if isinstance(member.value, str) and member.value.casefold() == normalized:
            return member
        if isinstance(member.value, int):
            try:
                if int(text) == member.value:
                    return member
            except ValueError:
                pass
    raise KeyError(value)


def enum_query_values(target_type: type[Enum]) -> list[str]:
    """返回 Web query 接收的枚举名称和值文本."""
    values: list[str] = []
    seen: set[str] = set()
    for member in iter_enum_members(target_type):
        candidates = [member.name]
        if isinstance(member.value, int | str):
            candidates.append(str(member.value))
        for candidate in candidates:
            if candidate not in seen:
                values.append(candidate)
                seen.add(candidate)
    return values
