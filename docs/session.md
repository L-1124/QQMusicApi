# Session

实现 QQ音乐 API 请求管理，基于协程上下文和线程隔离机制，支持多 Session 嵌套与并发场景。

## 核心特性

- 基于 `contextvars` 实现协程层级的 Session 上下文管理
- 自动线程隔离，不同线程使用独立 Session 实例
- 支持嵌套上下文管理器，协程内 Session 堆栈管理

## 基础用法

### 使用上下文管理器

```python
from qqmusic_api import Session

async def main():
    # 创建临时 Session 上下文
    async with Session() as session:
        # 在此上下文内的 API 请求使用此 Session
        ...
    # 退出后自动恢复之前的 Session
```

### 获取全局 Session

```python
from qqmusic_api import get_session

async def main():
    session = get_session()  # 获取当前事件循环的全局 Session
```

## 进阶配置

### 启用加密接口

```python
async def main():
    # enable_sign 启用请求签名
    async with Session(enable_sign=True) as session:
         ...
```


### 凭证管理

```python
from qqmusic_api import Credential

async def main():
    # 全局凭证设置
    get_session().credential = Credential(...)

    # 上下文内覆盖凭证
    async with Session(credential=Credential(...)):
        ...
```

### 设置代理

```python
import httpx
from qqmusic_api import Session


async def main():
    async with Session(proxy="http://localhost:8030"):
        # 这个代码块的请求将会使用代理
        ...
    # or

    async with Session(
        mounts={
            "http://": httpx.AsyncHTTPTransport(proxy="http://localhost:8030"),
            "https://": httpx.AsyncHTTPTransport(proxy="http://localhost:8031"),
        }
    ):
        # 这个代码块的请求将会使用代理
        ...
```
