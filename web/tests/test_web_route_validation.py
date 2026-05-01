"""Web 路由契约校验测试."""

from qqmusic_api.modules.singer import TabType
from web.src.routing.route_types import PUBLIC_60, AuthPolicy, HttpMethod, ParamOverride, ParamSource, WebRoute
from web.src.routing.router_factory import validate_routes


def test_duplicate_path_method_rejected() -> None:
    """测试重复路径与方法会被拒绝."""
    routes = (
        WebRoute(module="search", method="get_hotkey", path="/dup", response_model=dict),
        WebRoute(module="search", method="get_hotkey", path="/dup", response_model=dict),
    )

    errors = validate_routes(routes)

    assert any("重复" in error for error in errors)


def test_unsupported_auto_query_param_rejected() -> None:
    """测试复杂 SDK 参数不能自动暴露为 Query."""
    route = WebRoute(module="search", method="general_search", path="/search/general_search", response_model=dict)

    errors = validate_routes((route,))

    assert any("不能自动表达" in error for error in errors)


def test_auth_cache_conflict_rejected() -> None:
    """测试认证路由不能使用 public 缓存."""
    route = WebRoute(
        module="search",
        method="get_hotkey",
        path="/search/hotkey",
        response_model=dict,
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        cache=PUBLIC_60,
    )

    errors = validate_routes((route,))

    assert any("认证路由不能使用 public 缓存" in error for error in errors)


def test_path_template_mismatch_rejected() -> None:
    """测试路径模板与 Path 参数不一致会被拒绝."""
    route = WebRoute(
        module="search",
        method="get_hotkey",
        path="/search/{keyword}",
        response_model=dict,
        param_overrides=(ParamOverride("value", ParamSource.PATH, annotation=str),),
    )

    errors = validate_routes((route,))

    assert any("路径参数" in error for error in errors)


def test_query_non_int_enum_requires_mapping() -> None:
    """测试 Query 非 IntEnum 参数必须声明显式映射."""
    route = WebRoute(
        module="search",
        method="get_hotkey",
        path="/search/tab",
        response_model=dict,
        param_overrides=(ParamOverride("tab_type", ParamSource.QUERY, annotation=TabType),),
    )

    errors = validate_routes((route,))

    assert any("非 IntEnum" in error for error in errors)


def test_valid_route_discovers_sdk_params() -> None:
    """测试合法路由会自动发现 SDK 参数."""
    route = WebRoute(
        module="search",
        method="complete",
        path="/search/complete",
        methods=(HttpMethod.GET,),
        response_model=dict,
    )

    assert validate_routes((route,)) == ()
