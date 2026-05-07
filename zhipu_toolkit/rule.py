import random

from zhenxun.utils.rules import ensure_group

from nonebot_plugin_uninfo import Uninfo

from .data_source import ImpersonationStatus

from .config import ChatConfig


async def need_byd(session: Uninfo) -> bool:
    return bool(
        ensure_group(session)
        and random.random() * 100 < ChatConfig.get("IMPERSONATION_TRIGGER_FREQUENCY")
        and await ImpersonationStatus.check(session)
    )
