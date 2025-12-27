"""推荐相关 API"""

from .utils.network import NO_PROCESSOR, api_request


@api_request("music.recommend.RecommendFeed", "get_recommend_feed")
async def get_home_feed():
    """获取主页推荐"""
    return {
        "direction": 0,
        "page": 1,
        "s_num": 0,
    }, NO_PROCESSOR


@api_request("music.radioProxy.MbTrackRadioSvr", "get_radio_track")
async def get_guess_recommend():
    """获取猜你喜欢"""
    return {
        "id": 99,
        "num": 5,
        "from": 0,
        "scene": 0,
        "song_ids": [],
        "ext": {"bluetooth": ""},
        "should_count_down": 1,
    }, NO_PROCESSOR


@api_request("music.recommend.TrackRelationServer", "GetRadarSong")
async def get_radar_recommend():
    """获取雷达推荐"""
    return {
        "Page": 1,
        # "LastToastTime": 1755782480,
        "ReqType": 0,
        "FavSongs": [],
        "EntranceSongs": [],
        # "ext": {"bluetooth": ""},
    }, NO_PROCESSOR


@api_request("music.playlist.PlaylistSquare", "GetRecommendFeed")
async def get_recommend_songlist():
    """获取推荐歌单"""
    return {"From": 0, "Size": 25}, NO_PROCESSOR


@api_request("newsong.NewSongServer", "get_new_song_info")
async def get_recommend_newsong():
    """获取推荐新歌"""
    return {"type": 5}, NO_PROCESSOR
