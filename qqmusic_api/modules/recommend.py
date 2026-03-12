"""推荐模块."""

from ._base import ApiModule


class RecommendApi(ApiModule):
    """推荐 API."""

    def get_home_feed(self):
        """获取主页推荐数据."""
        data = {
            "direction": 0,
            "page": 1,
            "s_num": 0,
        }
        return self._build_request("music.recommend.RecommendFeed", "get_recommend_feed", data)

    def get_guess_recommend(self):
        """获取猜你喜欢推荐数据."""
        data = {
            "id": 99,
            "num": 5,
            "from": 0,
            "scene": 0,
            "song_ids": [],
            "ext": {"bluetooth": ""},
            "should_count_down": 1,
        }
        return self._build_request("music.radioProxy.MbTrackRadioSvr", "get_radio_track", data)

    def get_radar_recommend(self):
        """获取雷达推荐数据."""
        data = {
            "Page": 1,
            "ReqType": 0,
            "FavSongs": [],
            "EntranceSongs": [],
        }
        return self._build_request("music.recommend.TrackRelationServer", "GetRadarSong", data)

    def get_recommend_songlist(self):
        """获取推荐歌单数据."""
        data = {"From": 0, "Size": 25}
        return self._build_request("music.playlist.PlaylistSquare", "GetRecommendFeed", data)

    def get_recommend_newsong(self):
        """获取推荐新歌数据."""
        data = {"type": 5}
        return self._build_request("newsong.NewSongServer", "get_new_song_info", data)
