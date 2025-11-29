import random

from nonebot import require
from nonebot.adapters import Event

from zhenxun.utils.rules import ensure_group

require("nonebot_plugin_uninfo")
from nonebot_plugin_uninfo import Uninfo

from .config import ChatConfig, nicknames


async def need_reply(event: Event) -> bool:
    if event.is_tome():
        return True
    msg = event.get_message().extract_plain_text()
    return all(nickname not in msg for nickname in nicknames)


async def need_byd(session: Uninfo) -> bool:
    return bool(
        ensure_group(session)
        and random.random() * 100 < ChatConfig.get("IMPERSONATION_TRIGGER_FREQUENCY")
    )
