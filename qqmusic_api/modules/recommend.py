"""推荐模块."""

from typing import Any, cast

from ..core.pagination import (
    CursorStrategy,
    MultiFieldContinuationStrategy,
    PagerMeta,
    PageStrategy,
    PaginationParams,
    ResponseAdapter,
)
from ..models.recommend import (
    GuessRecommendResponse,
    RadarRecommendResponse,
    RecommendFeedCardResponse,
    RecommendNewSongResponse,
    RecommendSonglistResponse,
)
from ._base import ApiModule


class RecommendApi(ApiModule):
    """推荐 API."""

    def get_home_feed(
        self,
        page: int = 1,
        direction: int = 0,
        s_num: int = 0,
        v_cache: list[str] | None = None,
    ):
        """获取主页推荐.

        Args:
            page: 页码.
            direction: 刷新方向.
            s_num: 已加载的卡片数量.
            v_cache: 已曝光的卡片 ID 缓存, 防止重复推荐.
        """
        data: dict[str, Any] = {
            "direction": direction,
            "page": page,
            "s_num": s_num,
        }
        if v_cache is not None:
            data["v_cache"] = v_cache

        def _build_home_feed_next_params(
            params: PaginationParams,
            response: RecommendFeedCardResponse,
            adapter: ResponseAdapter,
        ) -> PaginationParams | None:
            shelf_count = adapter.get_count(response) or 0
            if shelf_count <= 0:
                return None

            next_params = cast("dict[str, Any]", params)
            seen = {str(item) for item in next_params.get("v_cache", [])}
            for shelf in response.shelves:
                shelf_id = str(shelf.id)
                if shelf_id not in seen:
                    seen.add(shelf_id)

            next_params["direction"] = 1
            next_params["page"] = int(next_params.get("page", 1)) + 1
            next_params["s_num"] = int(next_params.get("s_num", 0)) + shelf_count
            next_params["v_cache"] = list(seen)
            return next_params

        return self._build_request(
            "music.recommend.RecommendFeed",
            "get_recommend_feed",
            data,
            response_model=RecommendFeedCardResponse,
            pager_meta=PagerMeta(
                strategy=MultiFieldContinuationStrategy(
                    _build_home_feed_next_params,
                    context_name="recommend_home_feed",
                ),
                adapter=ResponseAdapter(count=lambda response: len(response.shelves)),
            ),
        )

    def get_guess_recommend(self):
        """获取猜你喜欢推荐."""
        data = {
            "id": 99,
            "num": 5,
            "from": 0,
            "scene": 0,
            "song_ids": [],
        }
        return self._build_request(
            "music.radioProxy.MbTrackRadioSvr",
            "get_radio_track",
            data,
            response_model=GuessRecommendResponse,
        )

    def get_radar_recommend(self, page: int = 1):
        """获取雷达推荐.

        Args:
            page: 页码.
        """
        data = {
            "Page": page,
            "ReqType": 0,
            "FavSongs": [],
            "EntranceSongs": [],
        }
        return self._build_request(
            "music.recommend.TrackRelationServer",
            "GetRadarSong",
            data,
            response_model=RadarRecommendResponse,
            pager_meta=PagerMeta(
                strategy=PageStrategy(page_key="Page", start_page=page),
                adapter=ResponseAdapter(has_more_flag="has_more"),
            ),
        )

    def get_recommend_songlist(self, page: int = 1, num: int = 25):
        """获取推荐歌单.

        Args:
            page: 页码.
            num: 返回推荐歌单数量.
        """
        data = {"From": num * (page - 1), "Size": num}
        return self._build_request(
            "music.playlist.PlaylistSquare",
            "GetRecommendFeed",
            data,
            response_model=RecommendSonglistResponse,
            pager_meta=PagerMeta(
                strategy=CursorStrategy(cursor_key="From"),
                adapter=ResponseAdapter(has_more_flag="has_more", cursor="from_limit"),
            ),
        )

    def get_recommend_newsong(self):
        """获取推荐新歌."""
        data = {"type": 5}
        return self._build_request(
            "newsong.NewSongServer",
            "get_new_song_info",
            data,
            response_model=RecommendNewSongResponse,
        )
