# Credential

`Credential` 用于保存 QQ 音乐登录态相关数据，并在需要登录的接口中作为凭证使用。

## 核心字段

| 字段            | 类型  | 必需 | 说明                                                         |
|-----------------|-------|:----:|--------------------------------------------------------------|
| `musicid`       | `int` |  是  | 账号标识。QQ 登录通常是 QQ 号，微信登录通常是更长的数字 ID。 |
| `musickey`      | `str` |  是  | 登录态 Key，通常以 `Q_H_L_` 或 `W_X_` 开头。                 |
| `refresh_key`   | `str` |  否  | 用于刷新登录态。                                             |
| `refresh_token` | `str` |  否  | 用于刷新登录态。                                             |
| `encrypt_uin`   | `str` |  否  | 部分接口会返回的加密账号标识。                               |

## 常见组合

| `musickey` 前缀 | `musicid` 形态 | 说明         |
|-----------------|----------------|--------------|
| `Q_H_L_`        | 6-11 位数字    | QQ 账号登录  |
| `W_X_`          | 最长可到 19 位 | 微信账号登录 |

## 全局使用

```python
import asyncio

from qqmusic_api import Client, Credential


async def main() -> None:
    credential = Credential(musicid=123456, musickey="Q_H_L_xxx")

    async with Client(credential=credential) as client:
        result = await client.user.get_euin(credential.musicid)
        print(result)


asyncio.run(main())
```

## 单次请求覆盖

如果你不想把凭证绑定到整个 `Client`，需要 `Crential` 的接口都支持使用 `credential` 参数进行单次请求覆盖。

```python
import asyncio
from qqmusic_api import Client, Credential

async def main() -> None:
    async with Client() as client:
        credential = Credential(musicid=123456, musickey="Q_H_L_xxx")
        result = await client.song.get_song_urls(..., credential=credential)
        print(result)

asyncio.run(main())
```

## 刷新

可以通过 `client.login.check_expired` 和 `credential.is_expired()` 来判断是否过期。

!!! note

     `credential.is_expired()` 只是简单的通过时间戳判断是否过期

```python
import asyncio
from qqmusic_api import Client, Credential

async def main() -> None:
    async with Client() as client:
        credential = Credential(
            musicid=123456,
            musickey="Q_H_L_xxx",
            refresh_key="xxx",
            refresh_token="xxx",
            access_token="xxx",
        )
        await credential.refresh(client)
        print(credential.musicid, credential.musickey)

asyncio.run(main())
```

## 凭证快照与 Android 会话

每次请求执行前，客户端会捕获当前凭证。`Credential` 是不可变模型，因此可以安全共享引用；执行期间重新设置
`Client.credential` 不会影响正在执行的操作。

Android 平台的匿名会话值（uid/sid）属于设备，与账号凭证相互独立。指定 `device_path` 时会话随设备信息持久化；
首次业务请求获取会话，之后复用，并在跨自然日后的首次 Android 请求中刷新。
