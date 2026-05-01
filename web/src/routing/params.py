"""动态请求参数模型构造."""

from enum import Enum, IntEnum
from typing import Annotated, Any, get_args, get_origin

import orjson
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, WithJsonSchema, create_model

from .docstrings import enum_member_description
from .enum_utils import enum_mapping_param, int_enum_param, path_enum_param
from .route_types import ParamOverride, ParamSource


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
        if param.enum_mapping is not None:
            mapping_description = param.enum_mapping.description()
            field_kwargs["description"] = f"{description}\n\n{mapping_description}"
            if default is not ... and isinstance(default, Enum):
                default = param.enum_mapping.values[param.enum_mapping.members.index(default)]
        elif source is ParamSource.PATH and _is_enum_annotation(annotation):
            if default is not ... and isinstance(default, Enum):
                default = default.name.casefold()
        elif source is not ParamSource.PATH and _is_int_enum_annotation(annotation):
            if default is not ... and isinstance(default, IntEnum):
                default = int(default.value)
        raw_enum_type = _enum_type(param.annotation)
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
    enum_type = _enum_type(annotation)
    if enum_type is None:
        return annotation
    if param.source is ParamSource.PATH:
        return path_enum_param(enum_type)
    if issubclass(enum_type, IntEnum):
        return int_enum_param(enum_type)
    return annotation


def _is_enum_annotation(annotation: Any) -> bool:
    enum_type = _enum_type(annotation)
    return enum_type is not None


def _is_int_enum_annotation(annotation: Any) -> bool:
    enum_type = _enum_type(annotation)
    return enum_type is not None and issubclass(enum_type, IntEnum)


def _enum_type(annotation: Any) -> type[Enum] | None:
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return annotation
    origin = get_origin(annotation)
    if origin is None:
        return None
    for arg in get_args(annotation):
        enum_type = _enum_type(arg)
        if enum_type is not None:
            return enum_type
    return None


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
