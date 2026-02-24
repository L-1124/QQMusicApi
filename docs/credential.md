# 凭证（Cookie）

[`Credential`][models.request.Credential] 用于管理 QQ 音乐的账号数据

## 部分字段解释

| 字段          | 类型 |       必需       | 说明                                |
| ------------- | ---- | :--------------: | ----------------------------------- |
| musicid       | int  | :material-check: | QQ 登录为 QQ 号                     |
| musickey      | str  | :material-check: | 以`Q_H_L_`或`W_X_`开头的字符串      |
| refresh_key   | str  | :material-close: | 用于刷新已失效的`musickey`          |
| refresh_token | str  | :material-close: | 用于刷新已失效的`musickey`          |
| encrypt_uin   | str  | :material-close: | 加密后的`musicid`，用于获取账号信息 |

### `musicid` 和 `musickey` 说明

| musickey     | musicid  | 说明     |
| ------------ | -------- | -------- |
| `Q_H_L_`开头 | 6-11 位  | QQ 账号  |
| `W_X_`开头   | 最大19位 | 微信账号 |

## 全局使用

可以通过初始化 `Client` 来使用此 `Credential`：

```python
from qqmusic_api import Client, Credential

async def main():
    credential = Credential(...)
    # 将 credential 传递给 Client
    async with Client(credential=credential) as client:
        # 此 client 的所有请求都会带有 credential
        pass
```
