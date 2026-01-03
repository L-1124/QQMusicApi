"""
pytest配置文件 - 用于设置测试间隔和其他全局配置
"""

import asyncio
import random

import pytest


@pytest.fixture(scope="function", autouse=True)
async def add_delay_between_tests():
    yield  # 测试函数执行
    await asyncio.sleep(random.uniform(0.5, 1.5))
