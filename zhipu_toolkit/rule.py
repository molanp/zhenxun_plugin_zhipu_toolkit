from nonebot import require
from nonebot.adapters import Event

require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import Uninfo

from zhenxun.utils.platform import PlatformUtils

from .config import ChatConfig, nicknames


async def is_to_me(event: Event) -> tuple[bool, bool]:
    msg = event.get_message().extract_plain_text()
    for nickname in nicknames:
        if nickname in msg:
            return True, False
    return event.is_tome(), True


async def enable_qbot(session: Uninfo) -> bool:
    return (
        not PlatformUtils.is_qbot(session) or ChatConfig.get("ENBALE_QBOT") is not False
    )
