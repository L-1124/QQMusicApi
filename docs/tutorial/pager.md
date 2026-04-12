# Pager 与 Refresher

`paginate()` 用于按页消费已经声明连续翻页能力的请求结果。

与一次性请求单页数据不同，分页器会在每次迭代时自动请求下一页，并返回接口原本的响应模型。

`refresh()` 则用于“换一批”接口。它不会暴露异步迭代，而是返回 `ResponseRefresher`，由调用方按需手动请求下一批。

## Pager 基本用法

下面的示例会连续获取搜索结果的前 3 页：

```python
import asyncio

from qqmusic_api import Client


async def main() -> None:
    async with Client() as client:
        pager = client.search.search_by_type("周杰伦", num=5).paginate(limit=3)

        async for page in pager:
            print(page.nextpage)
            print(len(page.song))


asyncio.run(main())
```

## Pager 返回值

分页器每次迭代返回的，仍然是该接口原本的响应模型。

例如：

* `client.search.search_by_type(...).paginate()` 每一页返回 `SearchByTypeResponse`
* `client.songlist.get_detail(...).paginate()` 每一页返回 `GetSonglistDetailResponse`

这意味着你不需要学习新的分页包装类型，可以直接按原接口字段读取当前页数据。

## Pager 限制页数

`limit` 只控制最多迭代多少页，不会改写单页请求参数。

```python
import asyncio

from qqmusic_api import Client


async def main() -> None:
    async with Client() as client:
        pager = client.songlist.get_detail(songlist_id=7843129912, num=10).paginate(limit=2)
        pages = [page async for page in pager]
        print(len(pages))  # 2


asyncio.run(main())
```

如果不传 `limit`，分页器会一直请求，直到接口明确表示没有下一页。

## Refresher 基本用法

“换一批”接口先按普通请求获取当前批次，再通过 `refresh()` 取得控制器，由控制器的 `refresh()` 手动拉取下一批。

```python
import asyncio

from qqmusic_api import Client


async def main() -> None:
    async with Client() as client:
        request = client.song.get_related_mv(1114857)
        current_batch = await request
        refresher = request.refresh()
        next_batch = await refresher.refresh()

        print(current_batch.mv[0].id)
        print(next_batch.mv[0].id)


asyncio.run(main())
```

`ResponseRefresher` 不支持 `async for`，也不接受 `limit`。是否继续请求下一批，由调用方自己决定。

## 何时可以使用

并不是所有模块方法返回的请求对象都支持连续翻页或换一批。

* 只有声明了 `pager_meta` 的方法，返回的请求对象才会暴露 `paginate()`。
* 只有声明了 `refresh_meta` 的方法，返回的请求对象才会暴露 `refresh()`。

```python
pager = client.search.search_by_type("周杰伦").paginate()
refresher = client.song.get_related_mv(1114857).refresh()
```
