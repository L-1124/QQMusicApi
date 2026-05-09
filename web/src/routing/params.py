"""动态请求参数模型构造与枚举参数辅助函数."""

from enum import Enum, IntEnum
from typing import Annotated, Any, TypeVar, get_args, get_origin

import orjson
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, WithJsonSchema, create_model

from .docstrings import enum_member_description
from .route_types import EnumIntMapping, ParamOverride, ParamSource

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


def enum_type(annotation: Any) -> type[Enum] | None:
    """从类型注解中提取枚举类型."""
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation
    origin = get_origin(annotation)
    if origin is None:
        return None
    for arg in get_args(annotation):
        child_enum = enum_type(arg)
        if child_enum is not None:
            return child_enum
    return None


class RequestParamModel(BaseModel):
    """动态请求参数模型基类."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    def to_method_kwargs(self) -> dict[str, Any]:
        """转换为 SDK 方法参数."""
        return self.model_dump(exclude_unset=False)


def is_empty_model(model: type[BaseModel] | None) -> bool:
    """判断模型是否为空或不存在."""
    return model is None or not model.model_fields


def split_params(params: tuple[ParamOverride, ...]) -> dict[ParamSource, tuple[ParamOverride, ...]]:
    """按请求来源拆分参数声明."""
    return {source: tuple(param for param in params if param.source is source) for source in ParamSource}


def build_param_model(
    name: str,
    params: tuple[ParamOverride, ...],
    *,
    source: ParamSource,
    docs: dict[str, str] | None = None,
) -> type[RequestParamModel] | None:
    """按参数声明构造 Pydantic 请求模型."""
    if not params:
        return None
    fields: dict[str, Any] = {}
    for param in params:
        annotation = param.annotation if param.annotation is not None else Any
        annotation = _external_annotation(param, annotation)
        description = param.description or (docs or {}).get(param.name) or param.name
        field_kwargs: dict[str, Any] = {"description": description}
        if param.alias is not None:
            field_kwargs["alias"] = param.alias
        default = param.default
        raw_enum_type = enum_type(param.annotation)

        if param.enum_mapping is not None:
            mapping_description = param.enum_mapping.description()
            field_kwargs["description"] = f"{description}\n\n{mapping_description}"
            if default is not ... and isinstance(default, Enum):
                default = param.enum_mapping.values[param.enum_mapping.members.index(default)]
        elif source is ParamSource.PATH and raw_enum_type is not None:
            if default is not ... and isinstance(default, Enum):
                default = default.name.casefold()
        elif source is not ParamSource.PATH and raw_enum_type is not None and issubclass(raw_enum_type, IntEnum):
            if default is not ... and isinstance(default, IntEnum):
                default = int(default.value)

        if raw_enum_type is not None and param.enum_mapping is None and source is not ParamSource.PATH:
            member_desc = enum_member_description(raw_enum_type)
            if member_desc:
                field_kwargs["description"] = f"{description}\n\n{member_desc}"
        fields[param.name] = (annotation, Field(default=default, validate_default=True, **field_kwargs))
    return create_model(name, __base__=RequestParamModel, **fields)


def external_param_annotation(param: ParamOverride) -> Any:
    """返回参数面向 Web 的公开注解."""
    annotation = param.annotation if param.annotation is not None else Any
    return _external_annotation(param, annotation)


def _json_query_param(annotation: Any) -> Any:
    """返回 JSON Query 参数注解."""
    return Annotated[annotation, BeforeValidator(_parse_json_query), WithJsonSchema({"type": "object"})]


def _parse_json_query(value: Any) -> Any:
    """将 Query 中的 JSON 字符串解析为对象."""
    if value is None or isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        parsed = orjson.loads(text)
        if not isinstance(parsed, dict):
            raise TypeError("JSON query value must be an object")
        return parsed
    raise TypeError("JSON query value must be an object string")


def _external_annotation(param: ParamOverride, annotation: Any) -> Any:
    if param.enum_mapping is not None:
        return enum_mapping_param(param.enum_mapping)
    if param.source is ParamSource.QUERY and _is_dict_annotation(annotation):
        return _json_query_param(annotation)
    raw_enum_type = enum_type(annotation)
    if raw_enum_type is None:
        return annotation
    if param.source is ParamSource.PATH:
        return path_enum_param(raw_enum_type)
    if issubclass(raw_enum_type, IntEnum):
        return int_enum_param(raw_enum_type)
    return annotation


def _is_dict_annotation(annotation: Any) -> bool:
    """判断注解是否为 dict 或可选 dict."""
    if annotation is dict:
        return True
    origin = get_origin(annotation)
    if origin is dict:
        return True
    if origin is None:
        return False
    return any(arg is not type(None) and _is_dict_annotation(arg) for arg in get_args(annotation))
