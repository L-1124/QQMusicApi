"""获取歌手名称透明 PNG, 演示有图片和无特殊展示两种结果."""

import asyncio

from qqmusic_api import Client


async def main() -> None:
    """请求真实歌手名称展示信息并输出 JSON."""
    async with Client() as client:
        for mid in ("000qrPik2w6lDr", "0025NhlN2yWrP4"):
            result = await client.singer.get_name_special_display(mid)
            print(f"\nMID: {mid}")
            print(result.model_dump_json(indent=2))
            if result.display_type == 2 and result.pic_file:
                print(f"PNG: {result.pic_file}")
            else:
                print(f"无名称图片, 使用文字: {result.name}")


if __name__ == "__main__":
    asyncio.run(main())
