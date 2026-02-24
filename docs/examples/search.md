# 搜索

```python
import asyncio
from qqmusic_api import Client
from qqmusic_api.modules.search import SearchType
```

## 示例：综合搜索

```python
async def general_search_example():
    async with Client() as client:
        result = await client.search.general_search(
            "周杰伦",
            page=1,
            highlight=False,
        )
        print(result)
```

## 示例：类型搜索

```python
async def search_by_type_example():
    async with Client() as client:
        result = await client.search.search_by_type(
            "周杰伦",
            search_type=SearchType.SINGER,
            page=1,
            highlight=False,
        )
        print(result)
```

## 示例：快速搜索

```python
async def quick_search_example():
    async with Client() as client:
        result = await client.search.quick_search("周杰伦")
        print(result)
```
