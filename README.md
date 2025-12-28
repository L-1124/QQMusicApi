<div align="center">
    <a>
        <img src="https://socialify.git.ci/l-1124/QQMusicApi/image?description=1&font=Source%20Code%20Pro&language=1&logo=https%3A%2F%2Fy.qq.com%2Fmediastyle%2Fmod%2Fmobile%2Fimg%2Flogo.svg&name=1&pattern=Overlapping%20Hexagons&theme=Auto">
    </a>
    <a href="https://www.python.org">
        <img src="https://img.shields.io/badge/Python-3.10|3.11|3.12|3.13-blue" alt="Python">
    </a>
    <a href="https://github.com/l-1124/QQMusicApi?tab=MIT-1-ov-file">
        <img src="https://img.shields.io/github/license/l-1124/QQMusicApi" alt="GitHub license">
    </a>
    <a href="https://github.com/l-1124/QQMusicApi/stargazers">
        <img src="https://img.shields.io/github/stars/l-1124/QQMusicApi?color=yellow&label=Github%20Stars" alt="STARS">
    </a>
    <a href="https://github.com/l-1124/QQMusicApi/actions/workflows/testing.yml">
        <img src="https://github.com/l-1124/QQMusicApi/actions/workflows/testing.yml/badge.svg?branch=main" alt="Testing">
    </a>
</div>

---

> [!IMPORTANT]
> 本仓库的所有内容仅供学习和参考之用，禁止用于商业用途
>
> **音乐平台不易，请尊重版权，支持正版。**

**文档**: <a href="https://l-1124.github.io/QQMusicApi" target="_blank">https://l-1124.github.io/QQMusicApi</a>

**源代码**: <a href="https://github.com/l-1124/QQMusicApi" target="_blank">https://github.com/l-1124/QQMusicApi</a>

## 介绍

使用 Python 编写的用于调用 [QQ音乐](https://y.qq.com/) 各种 API 的库.

## 特色

- 涵盖常见 API
- 调用简便，函数命名易懂，代码注释详细
- 完全异步操作

## 依赖

- Cryptography
- HTTPX
- orjson

## 快速上手

### 安装

```bash
pip install qqmusic-api-python
```

### 使用

```python
import asyncio

from qqmusic_api import search

async def main():
    # 搜索歌曲
    result = await search.search_by_type(keyword="周杰伦", num=20)
    # 打印结果
    print(result)

asyncio.run(main())
```

## [Web API](./web/README.md)

## License

本项目基于 **[MIT License](https://github.com/l-1124/QQMusicApi?tab=MIT-1-ov-file)** 许可证发行。

## 免责声明

由于使用本项目产生的包括由于本协议或由于使用或无法使用本项目而引起的任何性质的任何直接、间接、特殊、偶然或结果性损害（包括但不限于因商誉损失、停工、计算机故障或故障引起的损害赔偿，或任何及所有其他商业损害或损失）由使用者负责

## 贡献者

[![Contributor](https://contrib.rocks/image?repo=l-1124/QQMusicApi)](https://github.com/l-1124/QQMusicApi/graphs/contributors)
