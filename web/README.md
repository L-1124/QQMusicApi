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
uv run uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后，访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看自动生成的 API 文档。

## 路由生成脚本

Web 路由声明以 `web/route_manifest.py` 为源数据。修改路由契约或简单请求模型后，应使用生成脚本同步自动生成区块。

### 校验生成结果

```bash
uv run python scripts/generate_web_routes.py --check
```

该命令会校验:

* `web/route_registry.py` 与 `web/query_models.py` 的自动生成区块是否最新。
* `web/route_manifest.py` 与运行时路由注册表是否一致。
* Path/Query 模型字段是否与 modules 方法签名匹配。

### 写入生成结果

```bash
uv run python scripts/generate_web_routes.py --write
```

该命令会根据 `web/route_manifest.py` 重写以下自动生成区块:

* `web/route_registry.py` 中的 generated imports。
* `web/route_registry.py` 中的 `ROUTE_CANDIDATES`。
* `web/query_models.py` 中的简单请求模型。

不要手动修改 generated block 内部内容；下一次执行 `--write` 会覆盖这些内容。

### 查看 manifest 草稿

```bash
uv run python scripts/generate_web_routes.py --print-manifest
```

该命令会根据当前运行时路由注册表打印 manifest 草稿，不会写入文件。

### 反向写入 manifest

```bash
uv run python scripts/generate_web_routes.py --write-manifest
```

该命令会根据当前运行时路由注册表重写 `web/route_manifest.py`。它主要用于迁移或修复场景；日常开发应优先手动维护 `web/route_manifest.py`，再执行 `--write`。

## 新增自动路由示例

在 `ROUTE_CONTRACTS` 中新增路由契约:

```python
RouteContract(
    module_attr="song",
    module_cls="SongApi",
    method_name="get_detail",
    path="/song/{value}/detail",
    response_model="GetSongDetailResponse",
    cache="PUBLIC_300",
    query_model="NoQuery",
    path_model="ValuePath",
)
```

字段说明:

* `module_attr`: `Client` 上的模块属性名。
* `module_cls`: modules 层 API 类名。
* `method_name`: modules 层方法名。
* `path`: Web 路由路径，Path 参数使用 `{name}`。
* `response_model`: 响应模型类名。
* `cache`: 缓存策略符号，支持 `PUBLIC_60`, `PUBLIC_300`, `PUBLIC_600` 或 `None`。
* `query_model`: Query 参数模型类名；自动路由必须提供。
* `path_model`: Path 参数模型类名；路径包含 Path 参数时必须提供。
* `auth`: 认证策略，默认 `none`；需要 Cookie 或默认凭据时使用 `cookie_or_default`。
* `adapter`: 默认 `auto`；手写显式路由使用 `explicit`。

## 新增简单请求模型示例

简单 Query/Path 模型写入 `REQUEST_MODEL_CONTRACTS`:

```python
RequestModelContract(
    name="ExamplePageQuery",
    base="AutoQueryModel",
    docstring="示例分页 Query.",
    fields=(
        FieldContract(
            name="page",
            annotation="int",
            description="页码.",
            default="1",
        ),
        FieldContract(
            name="num",
            annotation="int",
            description="返回数量.",
            default="10",
        ),
    ),
)
```

如果请求模型需要枚举转换、自定义 `to_method_kwargs()` 或其他特殊逻辑，应保留在 `web/query_models.py` 的手写区域，不要放入 `REQUEST_MODEL_CONTRACTS`。
