from nonebot.adapters import Event

from .config import nicknames


async def is_to_me(event: Event) -> tuple[bol, bool]:
    msg = event.get_message().extract_plain_text()
    for nickname in nicknames:
        if nickname in msg:
            return True, False
    return event.is_tome(), True
