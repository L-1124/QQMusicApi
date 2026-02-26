# Tarsio API 参考

## 目录

* [类型映射](#类型映射)
* [Public API 导出](#public-api-导出)
* [encode / decode 函数签名](#encode--decode-函数签名)
* [Struct 类方法](#struct-类方法)
* [field 函数](#field-函数)
* [Meta 约束](#meta-约束)
* [Inspect API](#inspect-api)
* [CLI 完整选项](#cli-完整选项)
* [协议格式](#协议格式)
* [已知问题](#已知问题)

## 类型映射

### 标量类型

| Python 类型 | 编码语义 | 说明 |
| --- | --- | --- |
| `int` | `ZeroTag` 或 `Int1/2/4/8` | 按值范围紧凑编码 |
| `float` | `ZeroTag` 或浮点类型 | `0.0` 走零值优化 |
| `bool` | 整型语义 | 协议层按数值处理 |
| `str` | `String1` / `String4` | 按 UTF-8 字节长度选择 |
| `bytes` | `SimpleList` | 接受 `bytearray`/`memoryview` |
| `Any` | 运行时分派 | 根据实际值决定编码分支 |

### 容器类型

| Python 类型               | 编码语义      | 解码结果            |
|---------------------------|---------------|---------------------|
| `list[T]`                 | `List`        | `list`              |
| `tuple[T1, T2, ...]`      | `List`        | `tuple`             |
| `tuple[T, ...]`           | `List`        | `tuple`             |
| `set[T]` / `frozenset[T]` | `List`        | `set` / `frozenset` |
| `dict[K, V]`              | `Map`         | `dict`              |
| `TarsDict`                | `Struct` 语义 | `TarsDict`          |

### 结构化类型

* `Struct` 子类: 推荐建模方式
* `Enum`: 按 `value` 的底层类型编码
* `Optional[T]` 或 `T | None`: `None` 时不写该字段
* `Union[A, B, ...]`: 按变体顺序匹配并编码

### typing 标记

* `Annotated[T, Meta(...)]`: 为 `T` 增加约束
* `Literal`, `NewType`, `Final`, 类型别名: 按展开后底层类型处理
* `Required` / `NotRequired`: 主要用于 `TypedDict` 字段语义

## Public API 导出

```python
from tarsio import (
    NODEFAULT,          # 哨兵值，标记无默认值
    Meta,               # 约束描述符
    Struct,             # Schema 基类
    StructConfig,       # 类配置快照
    StructMeta,         # Struct 元类
    TarsDict,           # Raw Struct 语义容器
    TraceNode,          # decode_trace 返回的追踪节点
    ValidationError,    # 约束校验失败异常
    decode,             # 统一解码入口
    decode_trace,       # 追踪解码（调试用）
    encode,             # 统一编码入口
    field,              # 字段描述符
    inspect,            # 类型内省模块
    probe_struct,       # 快速探测 bytes 是否为完整 Struct
)
```

## encode / decode 函数签名

```python
def encode(obj: Any) -> bytes:
    """将对象序列化为 Tars 二进制格式.

    自动分派:
    - TarsDict/dict/list/tuple/set/int/float/str/bytes/bool → Raw 编码
    - Struct → Schema 编码
    - 其他 → Raw 兜底

    Raises:
        TypeError: 不支持的类型
        ValueError: 数据校验失败
    """

def decode(data: bytes | bytearray | memoryview, cls: type = TarsDict) -> Any:
    """从 Tars 二进制反序列化.

    - cls 为 Struct 子类 → Schema 解码
    - 否则 → Raw 解码，返回 TarsDict

    Raises:
        TypeError: 参数类型错误或目标类未注册 Schema
        ValueError: 数据格式不正确
    """
```

## Struct 类方法

```python
class Struct:
    def encode(self) -> bytes: ...
    @classmethod
    def decode(cls, data: bytes | bytearray | memoryview) -> Self: ...
```

`Struct.decode(data)` 等价于 `decode(data, Struct)`。

## field 函数

```python
def field(
    *,
    tag: int | None = None,         # 显式 Tag (0-255)
    default: Any = NODEFAULT,       # 静态默认值
    default_factory: Callable = NODEFAULT,  # 工厂默认值
    wrap_simplelist: bool = False,  # 先编码再包装为 SimpleList(bytes)
) -> Any:
```

`tag` 未指定时按字段声明顺序自动分配。`default` 和 `default_factory` 互斥。

## Meta 约束

```python
class Meta:
    gt: int | float | None   # > 严格下界
    ge: int | float | None   # >= 下界
    lt: int | float | None   # < 严格上界
    le: int | float | None   # <= 上界
    min_len: int | None       # 字符串/容器最小长度
    max_len: int | None       # 字符串/容器最大长度
    pattern: str | None       # 正则匹配（仅字符串）
```

用法: `Annotated[int, Meta(ge=0, le=100)]`。约束在 decode 阶段校验，
失败抛 `ValidationError`。

## Inspect API

```python
from tarsio import inspect as tinspect

# 获取类型信息
info = tinspect.type_info(int)       # TypeInfo, kind="int"
info = tinspect.type_info(list[str]) # TypeInfo, kind="list"

# 获取 Struct 信息
schema = tinspect.struct_info(User)  # StructInfo
schema.fields[0].name  # "id"
schema.fields[0].tag   # 0
```

### TypeInfo.kind 取值

`int`, `str`, `float`, `bool`, `bytes`, `any`, `none`, `enum`, `union`,
`list`, `tuple`, `var_tuple`, `map`, `set`, `optional`, `struct`, `ref`

### StructInfo

```python
class StructInfo:
    name: str
    fields: list[FieldInfo]

class FieldInfo:
    name: str
    tag: int
    required: bool
    type_info: TypeInfo
    default: Any  # NODEFAULT if no default
```

## CLI 完整选项

```text
tarsio [ENCODED] [OPTIONS]

参数:
  ENCODED              hex 字符串，可含空格或 0x 前缀

选项:
  -f, --file PATH            从文件读取
  --file-format {bin,hex}    文件格式，默认 bin
  --probe {off,auto,on}      嵌套 bytes 探测策略，默认 auto
  --probe-max-bytes N        auto 模式单个 bytes 最大探测长度，默认 65536
  --probe-max-depth N        最大探测递归深度，默认 3
  --probe-max-nodes N        最多探测节点数，默认 256
  --format {pretty,json,tree} 输出格式，默认 pretty
  -o, --output PATH          输出到文件
  -v, --verbose              显示输入大小和 hex 摘要
```

`ENCODED` 与 `--file` 互斥。`tree` 格式基于 `decode_trace` 显示结构/tag/类型。

## 协议格式

Tars 协议采用 TLV (Tag-Type-Value) 格式，Big-Endian 字节序。

### Head 编码

* Tag < 15: 单字节 `[Tag(4bit) | Type(4bit)]`
* Tag >= 15: 双字节 `[0xF | Type(4bit)] [Tag(8bit)]`
* Tag 最大值 255

### Type ID

| ID | 名称        | 载荷                 |
|----|-------------|----------------------|
| 0  | Int1        | 1 字节               |
| 1  | Int2        | 2 字节 BE            |
| 2  | Int4        | 4 字节 BE            |
| 3  | Int8        | 8 字节 BE            |
| 4  | Float       | 4 字节 IEEE 754      |
| 5  | Double      | 8 字节 IEEE 754      |
| 6  | String1     | 1字节长度 + 内容     |
| 7  | String4     | 4字节长度 + 内容     |
| 8  | Map         | 长度 + KV 序列       |
| 9  | List        | 长度 + 元素序列      |
| 10 | StructBegin | 无                   |
| 11 | StructEnd   | 无                   |
| 12 | ZeroTag     | 无（值为 0）         |
| 13 | SimpleList  | Type + 长度 + 字节流 |

### 整数紧凑编码

值为 0 → ZeroTag(12)，`[-128,127]` → Int1，`[-32768,32767]` → Int2，
`[-2^31,2^31-1]` → Int4，其他 → Int8。

## 已知问题

### 动态 Struct 子类的内存增长

在无界循环中持续创建新 `Struct` 子类并实例化可能导致内存增长。

规避方案:

* 优先缓存并复用 Struct 类型
* 动态 schema 放独立 worker 进程并周期性重启
* 增加内存监控告警

静态 schema 项目不受影响。
