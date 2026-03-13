# 登录

```python
import asyncio

from qqmusic_api import Client
from qqmusic_api.modules.login import QRCodeLoginEvents, QRLoginType


async def main() -> None:
    async with Client() as client:
        qr = await client.login.get_qrcode(QRLoginType.QQ)
        qr.save("./qrcode")

        async for event, credential in client.login.iter_qrcode_login(qr, timeout_seconds=180):
            print(event)
            if event == QRCodeLoginEvents.DONE and credential is not None:
                print(credential)
                break


asyncio.run(main())
```
