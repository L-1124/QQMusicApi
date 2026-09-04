"""CGI 端点声明. 以纯数据描述一次上游 CGI 调用, 解析语义对齐旧 CgiRequest."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from ..core.request import AllowErrorCodes, _build_result
from ..core.versioning import Platform
from .errcode import resolve_cgi_error


@dataclass(frozen=True, kw_only=True)
class CgiEndpoint:
    """CGI 端点声明.

    Attributes:
        module: 请求所属的模块名称.
        method: 请求的方法名称.
        response_model: 期望的响应模型类型, 支持 Pydantic BaseModel.
        platform: 可选的平台标识, 优先于上下文默认平台.
        sign: 指示该请求是否需要签名处理.
        require_login: 请求是否需要凭证.
        allow_error_codes: 允许的错误码集合, 命中时不抛出异常.
        parse_on_allow: 命中允许的错误码时仍尝试解析响应数据, 优先级大于 `disable_parse`.
        disable_parse: 是否禁用响应解析, 直接返回原始 data 字典.
        preserve_bool: 是否在参数中保留布尔值 (而非转换为整型).
    """

    module: str
    method: str
    response_model: type[BaseModel] | None = None
    platform: Platform | None = None
    sign: bool = False
    require_login: bool = False
    allow_error_codes: AllowErrorCodes | None = None
    parse_on_allow: bool = False
    disable_parse: bool = False
    preserve_bool: bool = False

    def parse_data(self, raw_data: dict[str, Any]) -> Any:
        """按旧 CgiRequest._parse_response 相同语义解析单条 CGI 子响应.

        Args:
            raw_data: CGI 批量信封中的单条子响应 (含 code 与 data).

        Returns:
            解析结果 (模型实例或字典).

        Raises:
            CgiApiException: 业务错误码经注册表映射后抛出.
        """
        code = raw_data.get("code", 0)
        data = raw_data.get("data", {})

        if self.allow_error_codes == "all" or (self.allow_error_codes is not None and code in self.allow_error_codes):
            if self.parse_on_allow:
                return _build_result(data, self.response_model)
            return raw_data

        if error := resolve_cgi_error(code, data):
            raise error

        if self.disable_parse:
            return data
        return _build_result(data, self.response_model)
