# Pagination

QQMusicApi 提供了统一的分页体系：

* **`PaginatedCgiRequest`**：具备连续翻页与批次刷新能力的 CGI 请求描述符。既可直接 `await` 获取首批响应，也可通过 `.pager()`
  手动按需步进，或使用 `.paginate()`、`.collect()` 和 `async for` 进行流式与批量遍历。
* **`ItemPaginatedCgiRequest`**：具备数据项提取能力的分页扩展类。除具备通用分页方法外，还通过 `.iter_items()` 与
  `.collect_items()` 实现了跨越页面边界、直接消费单一具体业务元素（如歌曲、专辑等）的功能。

## 1. 单次请求与无状态步进

即使请求具备分页能力，你依然可以像普通请求一样直接 `await` 它，仅拉取单页数据：

```python
import asyncio
from qqmusic_api import Client


async def main() -> None:
    async with Client() as client:
        # 仅获取第 1 页数据
        first_page = await client.album.get_new_album(page=1, num=10)
        print(len(first_page.albums))


asyncio.run(main())
```

如果你希望配合上一次响应手动构建下一页请求：

```python
req1 = client.album.get_new_album(page=1, num=10)
res1 = await req1

# 根据上一次响应获取下一次请求的描述符
req2 = req1.next_request(res1)
if req2 is not None:
    res2 = await req2
```

## 2. 有状态控制器

通过 `.pager()` 可以创建一个有状态的 `AsyncPager` 控制器：

```python
import asyncio
from qqmusic_api import Client


async def main() -> None:
    async with Client() as client:
        pager = client.comment.get_hot_comments(102065756, page_size=5).pager(limit=2)

        while pager.has_more():
            page = await pager.next()
            print(len(page.comments))


asyncio.run(main())
```

> `has_more()` 只读取当前分页器的内部状态，不会发起网络请求。`next()` 没有更多数据时会抛出 `StopAsyncIteration`。

!!! note "分页请求在 gather 中的语义"

    分页请求传入 `Client.gather()` 时仅代表 **当前页**, 只执行一次请求, 不会隐式抓取后续页。
    需要跨页收集时请使用 `.collect()`、`.paginate()` 或 `.iter_items()` 等分页接口。

## 3. 全量收集与条目平铺

如果你希望直接获取多页响应列表，或者直接获取展平后的所有实体数据项（如所有歌曲或专辑）。为防止无休止拉取带来的耗时与风控风险，强烈建议调用时始终设置合理的
`limit` 参数：

```python
import asyncio
from qqmusic_api import Client


async def main() -> None:
    async with Client() as client:
        req = client.singer.get_album_list(mid="0025NhlN2yWrP4")

        # 收集前 3 页的 Response 响应对象列表
        pages = await req.collect(limit=3)
        print(f"共获取 {len(pages)} 页响应")

        # 自动跨页展开提取前 25 个专辑实体
        albums = await req.collect_items(limit=25)
        print(f"共收集 {len(albums)} 个专辑实体")


asyncio.run(main())
```

## 4. 异步流式迭代

```python
import asyncio
from qqmusic_api import Client


async def main() -> None:
    async with Client() as client:
        req = client.search.search_by_type("周杰伦", num=5)

        # 方式 1：直接迭代对象本身，等价于 paginate()，连续翻页直至尾页
        async for page in req:
            print("当前页歌曲数:", len(page.song))
            break  # 演示示例：仅处理一页后退出

        # 方式 2：显式限制最大翻页数（推荐在生产环境中为循环设置合理的上限）
        async for page in req.paginate(limit=2):
            print("当前页歌曲数:", len(page.song))

        # 方式 3：跨页条目级别迭代（自动展平为实体）
        async for song in req.iter_items(limit=10):
            print("歌曲名:", song.name)


asyncio.run(main())
```

## 5. 批次刷新与单批次步进

部分关联或推荐类接口（如歌曲相关 MV、相似歌曲等）并非按传统的页码（Page）或偏移量（Offset）递增，而是 **按批次（Batch）** 持续更新内容。

对于此类以批次刷新为主、常通过单次触发拉取的场景，推荐使用有状态的分页控制器 `.pager()` 配合 `.first()` 与 `.next()`
精准控制每一批次的获取：

```python
import asyncio
from qqmusic_api import Client


async def main() -> None:
    async with Client() as client:
        # 1. 实例化分页控制器
        pager = client.song.get_related_mv(1114857).pager()

        # 2. 首次加载页面时，拉取首批推荐数据
        first_batch = await pager.first()
        print("首批 MV 数量:", len(first_batch.mv))

        # 3. 按需触发：调用 pager.next() 刷新拉取下一个批次
        if pager.has_more():
            next_batch = await pager.next()
            print("下一批 MV 数量:", len(next_batch.mv))


asyncio.run(main())
```

通过 `pager().first()` 与 `pager().next()`，既能在规范的接口契约下享受自动游标维护与防重复终止保护，又能贴合按批次更新的数据消费模式。

## 6. 动态数据项提取

如果你使用的某个 API 返回的请求对象是原生的 `PaginatedCgiRequest`（即 API 层没有预设数据项提取器），你仍然可以通过
`.with_extractor()` 动态注入一个提取逻辑。这会将请求无缝转换为具备跨页提取能力的 `ItemPaginatedCgiRequest`。

这在处理一些层级较深、或者没有统一结构的响应时非常有用：

```python
import asyncio
from qqmusic_api import Client


async def main() -> None:
    async with Client() as client:
        # 这个 API 返回原生的 PaginatedCgiRequest
        req = client.search.general_search("周杰伦")

        # 动态绑定 extractor
        # 此时 item_req 类型变为 ItemPaginatedCgiRequest
        item_req = req.with_extractor(lambda r: r.song.items if r.song else [])

        # 现在你可以非常自然地跨页迭代数据项了！
        async for song in item_req.iter_items(limit=10):
            print("提取到的歌曲:", song)


asyncio.run(main())
```

!!! note "页间默认值"

    `collect()` 等连续分页的每一页都是一次独立操作：翻页之间修改 `Client.credential` 等默认值会影响 **下一页**。需要跨页稳定身份时，请在分页请求的描述符上显式绑定凭证。
