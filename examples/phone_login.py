"""手机验证码登录示例."""

import asyncio

from qqmusic_api import Client, LoginError
from qqmusic_api.models.login import PhoneLoginEvents
from qqmusic_api.modules.login_utils import PhoneLoginSession


async def phone_login_example() -> None:
    """手机验证码登录示例."""
    phone = 13000000000
    country_code = 86

    try:
        async with Client() as client:
            session = PhoneLoginSession(client.login, phone, country_code)
            result = await session.send_authcode()

            if result.event == PhoneLoginEvents.CAPTCHA:
                print(f"需要验证,访问链接: {result.info}")
                return
            if result.event == PhoneLoginEvents.FREQUENCY:
                print("操作过于频繁,请稍后再试")
                return

            print("验证码已发送")

            auth_code = (await asyncio.to_thread(input, "请输入验证码: ")).strip()
            credential = await session.authorize(auth_code)
            print(f"登录成功! MusicID: {credential.musicid}")

    except LoginError as e:
        print(f"登录失败: {e!s}")
    except ValueError:
        print("验证码必须为6位数字")
    except Exception as e:
        print(f"发生未知错误: {e!s}")


asyncio.run(phone_login_example())
