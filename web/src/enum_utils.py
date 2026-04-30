"""Web 层枚举查询参数辅助函数."""

from enum import Enum
from typing import Any


def iter_enum_members(target_type: type[Enum]) -> list[Enum]:
    """按目标枚举与子类枚举顺序返回成员."""
    members = list(target_type.__members__.values())
    for sub in target_type.__subclasses__():
        members.extend(iter_enum_members(sub))
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


def enum_query_values(target_type: type[Enum]) -> list[int | str]:
    """返回 Web query 文档展示的枚举名称和值."""
    values: list[int | str] = []
    seen: set[int | str] = set()
    for member in iter_enum_members(target_type):
        candidates: list[int | str] = [member.name.casefold()]
        if isinstance(member.value, int):
            candidates.append(member.value)
        elif isinstance(member.value, str):
            candidates.append(member.value.casefold())
        for candidate in candidates:
            if candidate not in seen:
                values.append(candidate)
                seen.add(candidate)
    return values


def flexible_enum_validator(enum_type: type[Enum]):
    """构建灵活枚举校验器(大小写不敏感,按名称后按值匹配)."""

    def validator(v: Any) -> Any:
        if isinstance(v, enum_type):
            return v
        text = str(v)
        normalized = text.casefold()
        for member in iter_enum_members(enum_type):
            if member.name.casefold() == normalized:
                return member
            if isinstance(member.value, str) and member.value.casefold() == normalized:
                return member
            if isinstance(member.value, int):
                try:
                    if int(text) == member.value:
                        return member
                except (ValueError, TypeError):
                    pass
        raise ValueError(f"无法解析为 {enum_type.__name__}: {v}")

    return validator
