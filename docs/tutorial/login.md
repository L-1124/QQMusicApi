# 登录

本教程介绍如何通过扫码或手机验证码获取 `Credential`，以及如何检查与刷新登录态。

## 扫码登录

库内置了 `QRCodeLoginSession` 封装完整的扫码轮询流程，支持 QQ、微信、QQ 音乐 APP 三种方式。

### 基本用法

```python
import asyncio

from qqmusic_api import Client, LoginError
from qqmusic_api.models.login import QRLoginType
from qqmusic_api.modules.login_utils import QRCodeLoginSession


async def main() -> None:
    async with Client() as client:
        session = QRCodeLoginSession(
            client.login,
            QRLoginType.QQ,  # QQ / WX / MOBILE
            interval=1.5,
            timeout_seconds=180.0,
        )
        qr = await session.get_qrcode()
        # 将 qr.data 写入文件或在终端渲染
        qr.save("./qrcode")

        print("请扫码...")
        credential = await session.wait_qrcode_login()
        print(f"登录成功! MusicID: {credential.musicid}")


asyncio.run(main())
```

### 三种扫码方式

| `QRLoginType` | 扫码客户端  | 说明                         |
|---------------|-------------|------------------------------|
| `QQ`          | 手机 QQ     | 传统 QQ 授权登录             |
| `WX`          | 微信        | 微信开放平台授权             |
| `MOBILE`      | QQ 音乐 APP | 通过 MQTT 长连接实时推送状态 |

### 监听登录事件流

如果需要在扫码过程中执行自定义逻辑（如更新 UI 状态），可以遍历事件流：

```python
from qqmusic_api.models.login import QRCodeLoginEvents

async for result in session.iter_events():
    match result.event:
        case QRCodeLoginEvents.SCAN:
            print("已扫码，等待确认...")
        case QRCodeLoginEvents.CONF:
            print("已确认，登录中...")
        case QRCodeLoginEvents.DONE:
            credential = result.credential
            break
        case QRCodeLoginEvents.REFUSE:
            print("用户拒绝了登录")
            break
        case QRCodeLoginEvents.TIMEOUT:
            print("二维码已过期")
            break
```

!!! note

    默认不产出重复的同类型事件。如需每次都收到回调，设置 `emit_repeat=True`。

### 轮询间隔控制

通过 `PollInterval` 可精细控制不同阶段的轮询频率：

```python
from qqmusic_api.modules.login_utils import PollInterval

session = QRCodeLoginSession(
    client.login,
    QRLoginType.QQ,
    interval=PollInterval(
        default=1.5,        # 默认轮询间隔
        scanned=0.8,        # 已扫码后加快轮询
        error=3.0,          # 网络错误时的退避间隔
    ),
)
```

## 手机验证码登录

通过 `PhoneLoginSession` 可完成手机号 + 验证码的登录流程。

### 基本用法

```python
import asyncio

from qqmusic_api import Client, LoginError
from qqmusic_api.models.login import PhoneLoginEvents
from qqmusic_api.modules.login_utils import PhoneLoginSession


async def main() -> None:
    async with Client() as client:
        session = PhoneLoginSession(client.login, phone=13000000000, country_code=86)
        result = await session.send_authcode()

        match result.event:
            case PhoneLoginEvents.SEND:
                print("验证码已发送")
            case PhoneLoginEvents.CAPTCHA:
                print(f"需要完成人机验证: {result.info}")
                return
            case PhoneLoginEvents.FREQUENCY:
                print("操作过于频繁，请稍后再试")
                return

        auth_code = input("请输入验证码: ")
        credential = await session.authorize(auth_code)
        print(f"登录成功! MusicID: {credential.musicid}")


asyncio.run(main())
```

## 凭证管理

### 检查是否过期

```python
# 通过 Client 检查（会请求服务端验证）
is_expired = await client.login.check_expired(credential)

# 通过 Credential 本地时间戳判断
is_expired = credential.is_expired()
```

### 刷新凭证

当凭证过期但 `refresh_key` / `refresh_token` 仍有效时，可尝试刷新：

```python
from qqmusic_api import Client, Credential

credential = Credential(
    musicid=123456,
    musickey="Q_H_L_xxx",
    refresh_key="xxx",
    refresh_token="xxx",
    access_token="xxx",
)

async with Client() as client:
    new_credential = await client.login.refresh_credential(credential)
    print(new_credential.musickey)
```

!!! warning

    刷新失败会抛出 `CredentialRefreshError`。此时需要重新登录。

## 完整示例

更多完整示例可参考 [examples/](https://github.com/L-1124/QQMusicApi/tree/main/examples)：

* `qrcode_login.py` — QQ / 微信 / QQ 音乐 APP 扫码登录
* `phone_login.py` — 手机验证码登录
