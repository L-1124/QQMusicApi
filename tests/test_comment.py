import pytest

from qqmusic_api.comment import (
    get_comment_count,
    get_hot_comments,
    get_moment_comments,
    get_new_comments,
    get_recommend_comments,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_get_hot_comments():
    comment = await get_hot_comments("542574330", 1, 10)
    assert comment


async def test_get_new_comments():
    comment = await get_new_comments("542574330", 1, 10)
    assert comment


async def test_get_recommend_comments():
    comment = await get_recommend_comments("542574330", 1, 10)
    assert comment


async def test_get_moment_comments():
    comment = await get_moment_comments(
        "542574330",
        10,
    )
    assert comment


async def test_get_comment_count():
    assert await get_comment_count("103540151")
