# Web Port 使用说明

## 安装与运行

### 克隆仓库

```bash
git clone https://github.com/luren-dc/QQMusicApi
cd QQMusicApi
```

### 安装 Web 依赖

```bash
uv sync --group web
```

### 启动服务

```bash
uv run web/run.py
```

服务启动后，访问 [http://localhost:8080/docs](http://localhost:8080/docs) 查看自动生成的 API 文档。

## 代码结构

* `web/src/app.py`: FastAPI 应用入口。
* `web/src/core/`: 配置、缓存、凭据、依赖、响应与安全中间件等基础设施。
* `web/src/routing/`: 类型化路由 DSL、参数模型构造、执行器、文档提取与路由注册工厂。
* `web/src/routes/`: 唯一公开 Web 路由契约表。
* `web/src/modules/`: 特殊路由适配器与专用请求/响应模型。

## 路由契约

Web 路由声明以 `web/src/routes/` 包中的 `ROUTES` 为唯一契约源。运行时只按显式 allowlist 注册路由，不扫描或自动暴露 `qqmusic_api.modules.*` 的所有公开方法。

新增路由时使用 `R()` 与 `P()` / `Q()` 辅助函数声明路由:

```python
from ._helpers import P, Q, R

R(
    module="song",
    method="get_detail",
    path="/song/{value}/detail",
    response_model=GetSongDetailResponse,
    params=(P("value", int | str, "资源 ID 或 MID."),),
    cache=PUBLIC_300,
)
```

字段说明:

* `module`: `Client` 上的模块属性名。
* `method`: modules 层方法名。
* `path`: Web 路由路径，Path 参数使用 `{name}`。
* `response_model`: 响应模型类。
* `params`: Path、Query、Body 参数声明，使用 `P()` 声明 Path 参数、`Q()` 声明 Query 参数，或直接传入 `ParamOverride` 元组。
* `cache`: 缓存策略，支持 `PUBLIC_60`, `PUBLIC_300`, `PUBLIC_600` 或 `None`。
* `auth`: 认证策略，默认 `AuthPolicy.NONE`；需要 Cookie 或默认凭据时使用 `AuthPolicy.COOKIE_OR_DEFAULT`。
* `adapter`: 特殊路由适配函数。适配器只承载特殊调用逻辑，路由元数据仍必须来自 `WebRoute`。

应用启动会调用 `validate_routes(ROUTES)` 校验路径、参数来源、SDK 方法签名、认证与缓存冲突，以及枚举公开形式。

## 枚举参数规则

* Query / Body 中的 `IntEnum` 只暴露整数值。例如 `SearchType.SONG` 使用 `0`，不接受 `song`、`searchtype.song` 或 `SearchType.SONG`。
* Path 中的枚举只暴露小写成员名。例如歌手 Tab 路由使用 `/singer/{mid}/tabs/wiki`。
* Query / Body 中的非 `IntEnum` 必须声明显式稳定整数映射。例如歌曲文件类型使用整数映射，不接受 `songfiletype.mp3_128`、`mp3_128` 或底层元组值。
* 二维码登录路由使用 Path 枚举: `/login/qrcode/{login_type}` 与 `/login/qrcode/{login_type}/status`，其中 `login_type` 当前支持 `qq` 与 `wx`。

## 特殊路由适配器

复杂路由在 `web/src/modules/` 中保留请求/响应模型与适配函数，例如歌曲文件链接、二维码登录、歌单写操作。适配器接收 `RouteContext`，从 `context.params` 读取已校验参数，并调用 SDK 方法。所有注册、OpenAPI 元数据、认证与缓存策略仍由 `web/src/routes/` 统一声明。
