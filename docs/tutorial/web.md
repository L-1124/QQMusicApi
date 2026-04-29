# Web 服务

Web 服务将 QQMusicApi 暴露为 HTTP API。

## 1. 安装

```bash
git clone https://github.com/luren-dc/QQMusicApi
cd QQMusicApi
uv sync --group web
```

可使用环境变量或者编辑`web/config.toml` 来配置服务参数

## 2. 启动服务

```bash
uv run python web/run.py
```

## 3. 查看 API 文档

打开 [http://localhost:8000/docs](http://localhost:8000/docs) 可以查看所有可用接口。

## 4. 认证方式

需要登录凭证的接口通过 **Cookie** 传递 QQ 音乐登录信息：

| Cookie 字段 | 说明 | 是否必须 |
| --- | --- | --- |
| `musicid` | QQ 音乐用户 ID | ✅ 必须 |
| `musickey` | QQ 音乐密钥 | ✅ 必须 |
| `openid` | QQ 音乐 OpenID | 可选 |
| `refresh_token` | Refresh Token | 可选 |
| `access_token` | Access Token | 可选 |
| `expired_at` | 登录态过期时间戳 | 可选 |
| `unionid` | UnionID | 可选 |
| `str_musicid` | 字符串形式的用户 ID | 可选 |
| `refresh_key` | Refresh Key | 可选 |

`musicid` 与 `musickey` 必须同时提供；如果未携带任何 Cookie，接口将以未登录状态调用。

## 5. 响应格式

所有接口均返回统一的 JSON 结构：

```json
{
  "code": 0,
  "msg": "ok",
  "data": { ... }
}
```

| 字段 | 说明 |
| --- | --- |
| `code` | 状态码。成功为 `0`，失败为 `-1`。 |
| `msg` | 面向调用方的状态说明。 |
| `data` | 业务数据，失败时可能包含错误详情。 |

## 6. 请求示例

### 搜索歌曲

```bash
curl "http://localhost:8000/search/search_by_type?keyword=周杰伦&search_type=song&num=5"
```

### 获取歌曲详情

```bash
curl "http://localhost:8000/song/123456/detail"
```

### 获取歌词（需要歌曲 ID 或 MID）

```bash
curl "http://localhost:8000/song/123456/lyric?trans=true"
```
