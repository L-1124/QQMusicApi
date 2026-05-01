"""SDK 方法文档字符串提取."""

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from griffe import (
    Docstring,
    DocstringAdmonition,
    DocstringAttribute,
    DocstringParameter,
    DocstringRaise,
    DocstringReturn,
    DocstringSectionKind,
)


@dataclass(frozen=True)
class MethodDocs:
    """SDK 方法文档内容."""

    summary: str
    description: str
    params: dict[str, str]
    returns: str | None = None
    raises: dict[str, str] = field(default_factory=dict)


def load_method_docs(method: Callable[..., Any]) -> MethodDocs:
    """从 SDK 方法文档字符串中提取 OpenAPI 可用文档."""
    docstring = inspect.getdoc(method) or ""
    if not docstring:
        return MethodDocs(summary="", description="", params={})
    parsed = Docstring(docstring).parse("google", warnings=False, warn_missing_types=False)
    text_sections: list[str] = []
    params: dict[str, str] = {}
    returns: str | None = None
    raises: dict[str, str] = {}
    for section in parsed:
        if section.kind is DocstringSectionKind.text:
            text_sections.append(str(section.value).strip())
        elif section.kind is DocstringSectionKind.admonition:
            if isinstance(section.value, DocstringAdmonition):
                annotation = str(section.value.annotation or "note")
                description = str(section.value.description).strip()
                text_sections.append(f"{annotation.title()}: {description}")
        elif section.kind is DocstringSectionKind.parameters:
            for parameter in section.value:
                if isinstance(parameter, DocstringParameter):
                    params[parameter.name] = str(parameter.description).strip()
        elif section.kind is DocstringSectionKind.returns:
            return_items = [item for item in section.value if isinstance(item, DocstringReturn)]
            if return_items:
                returns = "\n".join(str(item.description).strip() for item in return_items).strip() or None
        elif section.kind is DocstringSectionKind.raises:
            for item in section.value:
                if isinstance(item, DocstringRaise):
                    raises[str(item.annotation)] = str(item.description).strip()
    summary, description = _split_text_sections(text_sections)
    return MethodDocs(summary=summary, description=description, params=params, returns=returns, raises=raises)


def load_class_field_docs(cls: type) -> dict[str, str]:
    """从类文档字符串的 Attributes 段提取字段描述."""
    docstring = cls.__doc__ or ""
    if not docstring:
        return {}
    parsed = Docstring(docstring).parse("google", warnings=False, warn_missing_types=False)
    for section in parsed:
        if section.kind is DocstringSectionKind.attributes:
            return {
                attr.name: str(attr.description).strip()
                for attr in section.value
                if isinstance(attr, DocstringAttribute)
            }
    return {}


def clean_schema_description(docstring: str) -> str:
    """将 Attributes 段转换为 markdown 列表, 避免 Swagger spotlight 渲染为大段文本."""
    if not docstring or "Attributes:" not in docstring:
        return docstring
    parsed = Docstring(docstring).parse("google", warnings=False, warn_missing_types=False)
    parts: list[str] = []
    for section in parsed:
        if section.kind is DocstringSectionKind.text:
            parts.append(str(section.value).strip())
        elif section.kind is DocstringSectionKind.attributes:
            items: list[str] = []
            for attr in section.value:
                if isinstance(attr, DocstringAttribute):
                    desc = str(attr.description).strip()
                    items.append(f"- **{attr.name}**: {desc}")
            if items:
                parts.append("\n".join(items))
    return "\n\n".join(part for part in parts if part).strip()


def _split_text_sections(text_sections: list[str]) -> tuple[str, str]:
    text = "\n\n".join(section for section in text_sections if section).strip()
    if not text:
        return "", ""
    lines = text.splitlines()
    summary = lines[0].strip().rstrip(".")
    description = "\n".join(lines[1:]).strip()
    return summary, description
