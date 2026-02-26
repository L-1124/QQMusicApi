---
name: tarsio
description: "Rust 核心驱动的高性能 Python Tars (JCE) 协议库。定义 Struct schema 进行二进制编解码，或使用 TarsDict 做无 schema 的 Raw 模式。使用场景：(1) 定义 JCE 请求/响应 Struct，(2) 使用 TarsDict 构造动态协议数据，(3) encode/decode 二进制数据，(4) wrap_simplelist 嵌套编码，(5) CLI 调试 JCE 二进制，(6) Meta 约束校验，(7) Schema 演进与版本兼容。触发词：tarsio, Tars, JCE, Struct, TarsDict, encode, decode, field, wrap_simplelist, jce.dumps, jce.loads。"
---

# Tarsio

Rust 核心驱动的高性能 Python Tars (JCE) 协议库。

## 安装

```bash
pip install tarsio
# CLI 需要额外依赖
pip install "tarsio[cli]"
```

## 快速上手

```python
from typing import Annotated
from tarsio import Struct, TarsDict, Meta, encode, decode, field

# 定义 Schema
class User(Struct):
    id: int = field(tag=0)
    name: str = field(tag=1)
    score: Annotated[int, Meta(ge=0)] = field(tag=2, default=0)

# 编码
data = encode(User(id=1, name="Ada"))
# 解码（Schema 模式）
user = User.decode(data)
# 解码（Raw 模式，返回 TarsDict）
raw = decode(data)
```

## Tag 分配

两种等价方式：

```python
# 方式一：field(tag=N) — 推荐稳定模型使用
class User(Struct):
    id: int = field(tag=0)
    name: str = field(tag=1)

# 方式二：Annotated[T, N] — 简洁写法
class User(Struct):
    id: Annotated[int, 0]
    name: Annotated[str, 1]
```

未显式指定 tag 时按字段声明顺序自动分配。`field(tag=...)` 与 `Annotated` 可混用。

## Struct 配置

通过类参数传入：

```python
class User(Struct, frozen=True, omit_defaults=True, forbid_unknown_tags=True):
    id: Annotated[int, 0]
```

| 配置                  | 默认    | 说明                     |
| --------------------- | ------- | ------------------------ |
| `eq`                  | `True`  | 启用 `__eq__`            |
| `order`               | `False` | 启用排序比较             |
| `frozen`              | `False` | 不可变，可哈希           |
| `omit_defaults`       | `False` | 编码跳过等于默认值的字段 |
| `repr_omit_defaults`  | `False` | repr 跳过默认值字段      |
| `forbid_unknown_tags` | `False` | 解码遇未知 Tag 报错      |

## 默认值

```python
class Cache(Struct):
    owner: str = field(tag=0, default="system")
    items: list[int] = field(tag=1, default_factory=list)
```

可定义 `__post_init__` 做初始化后校验：

```python
class Interval(Struct):
    low: int = field(tag=0)
    high: int = field(tag=1)

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValueError("`low` 不能大于 `high`")
```

## TarsDict（Raw 模式）

`TarsDict` 是 Raw Struct 语义容器，key 为 int (tag)：

```python
param = TarsDict({
    0: 150,
    1: 0,
    2: "hello",
})
data = encode(param)
result = decode(data)  # 返回 TarsDict
```

Raw 模式下，普通 `dict` 按 `Map` 语义编码，`TarsDict` 按 `Struct` 语义编码。

## wrap_simplelist

`Struct`/`TarsDict` 字段可设置 `wrap_simplelist=True`，先正常编码再包装为 `SimpleList(bytes)`：

```python
class JceRequestItem(Struct):
    module: str = field(tag=0, default="")
    method: str = field(tag=1, default="")
    param: TarsDict = field(tag=2, default_factory=TarsDict, wrap_simplelist=True)
```

解码时严格要求 wire 为 `SimpleList(bytes)`，不做回退。仅支持 `Struct`/`TarsDict` 字段。

## encode / decode API

```python
from tarsio import encode, decode

# encode 自动分派
encode(user)        # Struct → Schema 编码
encode(tars_dict)   # TarsDict → Raw Struct 编码
encode({"a": 1})    # dict → Map 编码
encode([1, 2, 3])   # list → List 编码
encode(42)          # 基本类型 → Raw 编码

# decode
User.decode(data)           # Schema 解码，返回 User
decode(data)                # Raw 解码，返回 TarsDict（默认）
decode(data, User)          # 等价于 User.decode(data)
decode(data, TarsDict)      # 显式 Raw 解码
```

## Meta 约束

通过 `Annotated` + `Meta` 表达，在 decode 阶段校验：

```python
class Product(Struct):
    price: Annotated[int, Meta(gt=0)] = field(tag=0)
    code: Annotated[str, Meta(min_len=1, max_len=16)] = field(tag=1)
```

| 约束                  | 含义            |
| --------------------- | --------------- |
| `gt` / `ge`           | 数值下界        |
| `lt` / `le`           | 数值上界        |
| `min_len` / `max_len` | 字符串/容器长度 |
| `pattern`             | 正则匹配        |

校验失败抛 `ValidationError`。

## Schema 演进

```python
class V1(Struct):
    id: int = field(tag=0)

class V2(Struct):
    id: int = field(tag=0)
    name: str | None = field(tag=1, default=None)  # 新增可选字段

# V1 读 V2 数据：未知 tag 被跳过
# V2 读 V1 数据：缺失字段用默认值
```

规则：不复用旧 tag，新增字段优先可选并提供默认值。

## 实际使用模式（JCE 请求/响应）

```python
from typing import Any
from tarsio import Struct, TarsDict, encode, field

class JceRequestItem(Struct):
    """JCE 请求项."""
    module: str = field(tag=0, default="")
    method: str = field(tag=1, default="")
    param: TarsDict = field(tag=2, default_factory=TarsDict, wrap_simplelist=True)

class JceRequest(Struct):
    """JCE 请求体."""
    comm: dict[str, Any] = field(tag=0)
    data: dict[str, JceRequestItem] = field(tag=1)

class JceResponseItem(Struct):
    """JCE 响应项."""
    code: int = field(tag=0, default=0)
    data: dict[int, Any] = field(tag=3, default_factory=dict)

class JceResponse(Struct):
    """JCE 响应体."""
    code: int = field(tag=0, default=0)
    data: dict[str, JceResponseItem] = field(tag=4, default_factory=dict)

# 构造请求
req = JceRequest(
    comm={"ct": "11", "cv": "14090008"},
    data={
        "req_0": JceRequestItem(
            module="music.shortUrl.sUrl",
            method="BatchLongToShort",
            param=TarsDict({0: [TarsDict({0: "https://...", 1: "backdoor"})]}),
        )
    },
)
payload = encode(req)

# 解析响应
resp = JceResponse.decode(response_bytes)
```

## CLI 调试

```bash
# 解析 hex
tarsio "00 64"

# 从文件读取
tarsio -f payload.bin --format json
tarsio -f payload.bin --format tree

# hex 文本文件
tarsio -f payload.hex --file-format hex
```

## 关键注意事项

* `TarsDict` 和 `dict` 编码语义不同：`TarsDict` → Struct 语义，`dict` → Map 语义
* `wrap_simplelist=True` 仅支持 `Struct`/`TarsDict` 字段
* `bytes` 字段同时接受 `bytearray`/`memoryview`，编码结果一致
* Tag 最大值 255，按 Big-Endian 编码
* 避免在无界循环中动态创建 `Struct` 子类（可能内存泄漏）
* 约束在 decode 阶段校验，encode 不做业务校验
* `Optional[T]` 或 `T | None`：`None` 时不写该字段

## 详细参考

* **完整类型映射表、Inspect API、CLI 详细选项**: 见 [references/api-reference.md](references/api-reference.md)
