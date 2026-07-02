# Web Port 使用说明

## 安装与运行

### 克隆仓库

```bash
git clone https://github.com/luren-dc/QQMusicApi
cd QQMusicApi
```

### 安装 Web 依赖

#### 方式 A

```bash
uv sync --group web --no-dev
```

#### 方式 B

```bash
pip install -r web/requirements.txt
```

### 启动服务

```bash
uv run --no-sync web/run.py
```

服务启动后，可通过以下地址查看 API 文档:

|                 地址                 | 说明               |
|:------------------------------------:|--------------------|
|    `http://localhost:8080/swagger`   | Swagger UI         |
|     `http://localhost:8080/redoc`    | ReDo               |
|     `http://localhost:8080/docs`     | Stoplight Elements |
| `http://localhost:8080/openapi.json` | OpenAPI            |

### Docker 部署

```bash
# 构建镜像
docker build -t qqmusic-api-web -f web/Dockerfile .

# 运行容器
docker run -d -p 8080:8080 --name qqmusic-api-web \
  -v ./web/data:/app/web/data \
  -v ./web/accounts.toml:/app/web/accounts.toml:ro \
  -v ./web/config.toml:/app/web/config.toml:ro \
  qqmusic-api-web
```

使用 docker-compose:

```bash
# 首次使用请复制示例文件并编辑:
cp web/docker-compose.example.yml web/docker-compose.yml
# 然后启动:
docker compose -f web/docker-compose.yml up -d
```

### wslc 部署

[`wslc`](https://learn.microsoft.com/zh-cn/windows/wsl/) 是 Windows 自带的 WSL 容器管理工具。

```bash
# 构建镜像
wslc build -t qqmusic-api-web -f web/Dockerfile .

# 运行容器
wslc run -d -p 8080:8080 --name qqmusic-api-web \
  -v ./web/data:/app/web/data \
  -v ./web/accounts.toml:/app/web/accounts.toml:ro \
  -v ./web/config.toml:/app/web/config.toml:ro \
  qqmusic-api-web
```

挂载说明:

* `web/data/` — 设备信息、凭据状态库、日志等持久化数据。
* `web/accounts.toml` — 可选，自定义全局凭据账号。
* `web/config.toml` — 可选，自定义 Web 配置。

配置通过环境变量覆盖，前缀 `QQMUSIC_`，嵌套字段用 `_` 分隔，例如 `QQMUSIC_SERVER_HOST=0.0.0.0`。

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

## 注意事项

* **限流与并发控制**在进程内存中实现，当 `workers > 1` 时每个 worker 独立计数，实际允许的请求速率会乘以 worker 数量。如需精确限流，请保持 `workers = 1` 或使用外部方案（如 Nginx、Redis）。
