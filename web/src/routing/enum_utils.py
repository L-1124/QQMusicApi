"""Web 层枚举参数辅助函数."""

from enum import Enum, IntEnum
from typing import Annotated, Any, TypeVar

from pydantic import BeforeValidator, WithJsonSchema

from .route_types import EnumIntMapping

EnumT = TypeVar("EnumT", bound=Enum)
IntEnumT = TypeVar("IntEnumT", bound=IntEnum)


def iter_enum_members(target_type: type[EnumT]) -> list[EnumT]:
    """按目标枚举与子类枚举顺序返回成员."""
    members = list(target_type.__members__.values())
    for sub in target_type.__subclasses__():
        members.extend(iter_enum_members(sub))
    return members


def int_enum_schema(enum_type: type[IntEnum]) -> dict[str, Any]:
    """返回 IntEnum 的整数 JSON Schema."""
    return {"type": "integer", "enum": [int(member.value) for member in iter_enum_members(enum_type)]}


def parse_int_enum(value: Any, enum_type: type[IntEnumT]) -> IntEnumT:
    """仅按整数值解析 IntEnum 成员."""
    if isinstance(value, IntEnum):
        raise TypeError("enum instance is not a valid external integer enum value")
    if isinstance(value, bool):
        raise TypeError("boolean is not a valid integer enum value")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        digits = text.removeprefix("-")
        if not digits.isdecimal():
            raise ValueError(f"not an integer enum value: {value}")
        parsed = int(text)
    else:
        raise TypeError(f"not an integer enum value: {value}")
    try:
        return enum_type(parsed)
    except ValueError as exc:
        allowed = ", ".join(str(member.value) for member in iter_enum_members(enum_type))
        raise ValueError(f"unsupported {enum_type.__name__} value: {value}. allowed: {allowed}") from exc


def int_enum_validator(enum_type: type[IntEnumT]):
    """构建 IntEnum 整数值校验器."""

    def validator(value: Any) -> IntEnumT:
        return parse_int_enum(value, enum_type)

    return validator


def int_enum_param(enum_type: type[IntEnumT]) -> Any:
    """返回可用于 Pydantic 字段的 IntEnum 参数注解."""
    return Annotated[
        enum_type, BeforeValidator(int_enum_validator(enum_type)), WithJsonSchema(int_enum_schema(enum_type))
    ]


def path_enum_value(member: Enum) -> str:
    """返回路径枚举成员的公开字符串值."""
    return member.name.casefold()


def path_enum_values(enum_type: type[EnumT]) -> list[str]:
    """返回路径枚举的公开字符串值列表."""
    return [path_enum_value(member) for member in iter_enum_members(enum_type)]


def parse_path_enum(value: Any, enum_type: type[EnumT]) -> EnumT:
    """仅按小写成员名解析路径枚举成员."""
    if not isinstance(value, str):
        raise TypeError(f"not a path enum value: {value}")
    values = {path_enum_value(member): member for member in iter_enum_members(enum_type)}
    try:
        return values[value]
    except KeyError as exc:
        allowed = ", ".join(values)
        raise ValueError(f"unsupported {enum_type.__name__} path value: {value}. allowed: {allowed}") from exc


def path_enum_schema(enum_type: type[Enum]) -> dict[str, Any]:
    """返回路径枚举字符串 JSON Schema."""
    return {"type": "string", "enum": path_enum_values(enum_type)}


def path_enum_validator(enum_type: type[EnumT]):
    """构建路径枚举校验器."""

    def validator(value: Any) -> EnumT:
        return parse_path_enum(value, enum_type)

    return validator


def path_enum_param(enum_type: type[EnumT]) -> Any:
    """返回可用于 Pydantic 字段的路径枚举参数注解."""
    return Annotated[
        enum_type, BeforeValidator(path_enum_validator(enum_type)), WithJsonSchema(path_enum_schema(enum_type))
    ]


def enum_mapping_schema(mapping: EnumIntMapping[Any]) -> dict[str, Any]:
    """返回显式枚举整数映射 JSON Schema."""
    return mapping.schema()


def enum_mapping_validator(mapping: EnumIntMapping[EnumT]):
    """构建显式枚举整数映射校验器."""

    def validator(value: Any) -> EnumT:
        return mapping.parse(value)

    return validator


def enum_mapping_param(mapping: EnumIntMapping[EnumT]) -> Any:
    """返回可用于 Pydantic 字段的显式枚举整数映射注解."""
    return Annotated[
        Any,
        BeforeValidator(enum_mapping_validator(mapping)),
        WithJsonSchema(enum_mapping_schema(mapping)),
    ]
