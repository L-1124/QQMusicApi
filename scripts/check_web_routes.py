"""校验 Web 路由契约快照与运行时注册表一致."""

import argparse
import inspect
import json
import re
from pathlib import Path
from textwrap import dedent
from typing import Any

from web.route_registry import AdapterKind, RouteSpec, get_route_specs

_ROUTE_TEMPLATE_RE = re.compile(r"{([^{}]+)}")
_MANIFEST_PATH = Path("web/route_manifest.py")


def _type_name(value: Any) -> str | None:
    """返回稳定的类型名称."""
    if value is None:
        return None
    return getattr(value, "__name__", str(value))


def _path_param_names(path: str) -> set[str]:
    """提取路由模板中的 Path 参数名."""
    return set(_ROUTE_TEMPLATE_RE.findall(path))


def _model_fields(model: Any) -> set[str]:
    """返回 Pydantic 模型字段集合."""
    if model is None:
        return set()
    return set(model.model_fields)


def _public_method_params(spec: RouteSpec) -> set[str]:
    """返回 modules 方法可由 Web 请求提供的参数名."""
    if spec.method is None:
        return set()
    signature = inspect.signature(spec.method)
    return {name for name in signature.parameters if name not in {"self", "credential"}}


def _required_method_params(spec: RouteSpec) -> set[str]:
    """返回 modules 方法必须由 Web 请求提供的参数名."""
    if spec.method is None:
        return set()
    signature = inspect.signature(spec.method)
    required: set[str] = set()
    for name, parameter in signature.parameters.items():
        if name in {"self", "credential"}:
            continue
        if parameter.default is inspect.Parameter.empty:
            required.add(name)
    return required


def _contract_kwargs(spec: RouteSpec) -> dict[str, Any]:
    """将运行时 RouteSpec 转换为可比较的契约字段."""
    return {
        "module_attr": spec.module_attr,
        "method_name": spec.method_name,
        "path": spec.path,
        "methods": spec.methods,
        "adapter": spec.adapter.value,
        "query_model": _type_name(spec.query_model),
        "path_model": _type_name(spec.path_model),
        "response_model": _type_name(spec.response_model),
        "cache_ttl": spec.cache.ttl,
        "cache_scope": spec.cache.scope,
        "auth": spec.auth.value,
        "router_name": spec.router_name,
    }


def _literal(value: Any) -> str:
    """返回符合项目引号风格的 Python 字面量."""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, tuple):
        items = ", ".join(_literal(item) for item in value)
        if len(value) == 1:
            items = f"{items},"
        return f"({items})"
    return repr(value)


def _format_contract(entry: dict[str, Any]) -> str:
    """格式化单条 manifest 契约."""
    lines = ["    RouteContract("]
    for key, value in entry.items():
        lines.append(f"        {key}={_literal(value)},")
    lines.append("    ),")
    return "\n".join(lines)


def manifest_content() -> str:
    """根据当前注册表生成 route manifest 内容."""
    contracts = [_contract_kwargs(spec) for spec in get_route_specs()]
    contract_items = "\n".join(_format_contract(contract) for contract in contracts)
    header = dedent(
        '''\
        """Web 路由契约快照."""

        from dataclasses import dataclass


        @dataclass(frozen=True)
        class RouteContract:
            """Web 路由契约快照项."""

            module_attr: str
            method_name: str
            path: str
            methods: tuple[str, ...]
            adapter: str
            query_model: str | None
            path_model: str | None
            response_model: str | None
            cache_ttl: int | None
            cache_scope: str | None
            auth: str
            router_name: str | None


        ROUTE_CONTRACTS: tuple[RouteContract, ...] = (
        '''
    )
    return f"{header}{contract_items}\n)\n"


def print_manifest() -> None:
    """打印 route manifest 草稿."""
    print(manifest_content(), end="")


def write_manifest() -> None:
    """写入 route manifest 快照."""
    _MANIFEST_PATH.write_text(manifest_content(), encoding="utf-8")
    print(f"Wrote {_MANIFEST_PATH}")


def _manifest_by_key(contracts: tuple[Any, ...]) -> dict[tuple[str, str], Any]:
    """按稳定路由键索引 manifest."""
    return {(contract.module_attr, contract.method_name): contract for contract in contracts}


def _spec_by_key(specs: tuple[RouteSpec, ...]) -> dict[tuple[str, str], RouteSpec]:
    """按稳定路由键索引运行时 RouteSpec."""
    return {(spec.module_attr, spec.method_name): spec for spec in specs}


def _check_manifest(specs: tuple[RouteSpec, ...]) -> list[str]:
    """校验 manifest 快照与运行时注册表一致."""
    from web.route_manifest import ROUTE_CONTRACTS

    errors: list[str] = []
    manifest = _manifest_by_key(ROUTE_CONTRACTS)
    runtime = _spec_by_key(specs)
    manifest_keys = set(manifest)
    runtime_keys = set(runtime)
    errors.extend(f"manifest 包含运行时不存在的路由: {key!r}" for key in sorted(manifest_keys - runtime_keys))
    errors.extend(f"运行时路由缺少 manifest 快照: {key!r}" for key in sorted(runtime_keys - manifest_keys))
    for key in sorted(manifest_keys & runtime_keys):
        contract = manifest[key]
        current = _contract_kwargs(runtime[key])
        for field_name, current_value in current.items():
            expected_value = getattr(contract, field_name)
            if expected_value != current_value:
                errors.append(
                    f"{key!r} 字段 {field_name} 不一致: manifest={expected_value!r}, runtime={current_value!r}"
                )
    return errors


def _check_models(specs: tuple[RouteSpec, ...]) -> list[str]:
    """校验 Path/Query 模型与 modules 方法签名一致."""
    errors: list[str] = []
    for spec in specs:
        key = (spec.module_attr, spec.method_name)
        path_fields = _model_fields(spec.path_model)
        query_fields = _model_fields(spec.query_model)
        path_params = _path_param_names(spec.path)
        if spec.adapter is AdapterKind.EXPLICIT:
            if spec.path_model is not None:
                errors.append(f"{key!r} 显式路由不能声明 path_model")
            if spec.query_model is not None:
                errors.append(f"{key!r} 显式路由不能声明 query_model")
            continue
        if spec.path_model is None and path_params:
            errors.append(f"{key!r} 模板路径缺少 path_model: {spec.path}")
        if spec.path_model is not None and path_params != path_fields:
            errors.append(f"{key!r} Path 模板参数与 path_model 字段不一致: {path_params!r} != {path_fields!r}")
        conflicts = path_fields & query_fields
        if conflicts:
            errors.append(f"{key!r} Path/Query 字段冲突: {sorted(conflicts)!r}")
        public_params = _public_method_params(spec)
        request_fields = path_fields | query_fields
        unknown_fields = request_fields - public_params
        if unknown_fields:
            errors.append(f"{key!r} 请求模型字段不在 modules 方法签名中: {sorted(unknown_fields)!r}")
        missing_required = _required_method_params(spec) - request_fields
        if missing_required:
            errors.append(f"{key!r} modules 必填参数未由 Path/Query 提供: {sorted(missing_required)!r}")
    return errors


def check() -> int:
    """执行全部 Web 路由契约校验."""
    specs = get_route_specs()
    errors = [*_check_manifest(specs), *_check_models(specs)]
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Web route contracts OK: {len(specs)} routes")
    return 0


def main() -> int:
    """命令行入口."""
    parser = argparse.ArgumentParser(description="校验或生成 Web 路由契约快照。")
    parser.add_argument("--print-manifest", action="store_true", help="根据当前 route_registry 打印 manifest 草稿。")
    parser.add_argument("--write-manifest", action="store_true", help="根据当前 route_registry 写入 manifest 快照。")
    args = parser.parse_args()
    if args.print_manifest:
        print_manifest()
        return 0
    if args.write_manifest:
        write_manifest()
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
