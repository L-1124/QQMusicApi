"""二维码登录示例."""

import asyncio
from pathlib import Path

from qqmusic_api import Client
from qqmusic_api.core.exceptions import LoginError
from qqmusic_api.modules.login import QR, QRCodeLoginEvents, QRLoginType


def show_qrcode(qr: QR) -> None:
    """显示二维码."""
    try:
        from terminal_qrcode import draw

        draw(qr.data).print(end="\n")
    except ImportError:
        # 保存二维码到当前目录
        save_path = qr.save(Path("./qrcode"))
        print(f"二维码已保存至: {save_path}")


async def qrcode_login_example(login_type: QRLoginType) -> None:
    """二维码登录示例."""
    try:
        async with Client(verify=False) as client:
            print(f"正在获取 {login_type.name} 二维码...")
            qr = await client.login.get_qrcode(login_type)
            print(f"获取 {login_type.name} 二维码成功")

            show_qrcode(qr)
            print(">>> 请使用对应客户端扫码")

            from contextlib import aclosing

            async with aclosing(
                client.login.iter_qrcode_login(
                    qr,
                    interval=1.5,
                    timeout_seconds=180.0,
                ),
            ) as qrcode_stream:
                async for event, credential in qrcode_stream:
                    print(f"当前状态: {event.name}")

                    if event == QRCodeLoginEvents.DONE and credential is not None:
                        print(f"登录成功! MusicID: {credential.musicid}")
                        return
                    if event == QRCodeLoginEvents.TIMEOUT:
                        print("二维码已过期,请重新获取")
                        return
                    if event == QRCodeLoginEvents.REFUSE:
                        print("用户拒绝了登录请求")
                        return

    except LoginError as e:
        print(f"登录失败: {e!s}")
    except Exception:
        raise


async def main() -> None:
    """运行二维码登录示例."""
    print("请选择登录方式:")
    print("1. QQ   (使用手机QQ扫码)")
    print("2. WX   (使用微信扫码)")
    print("3. MOBILE (使用QQ音乐APP扫码)")

    choice = (await asyncio.to_thread(input, "请输入选项 (1/2/3): ")).strip()
    # choice = input("请输入选项 (1/2/3): ").strip()

    if choice == "1":
        await qrcode_login_example(QRLoginType.QQ)
    elif choice == "2":
        await qrcode_login_example(QRLoginType.WX)
    elif choice == "3":
        await qrcode_login_example(QRLoginType.MOBILE)
    else:
        print("无效的选项")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n用户取消操作")
