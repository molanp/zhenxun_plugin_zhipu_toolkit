import nonebot
from ._model import Tool
from zhenxun.services.log import logger

class PokeMsg(Tool):
    """工具类：用于戳一戳指定用户"""

    def __init__(self):
        super().__init__(
            name="poke_user",
            description=(
                "用于戳一戳指定用户"
                "传入用户id发送戳一戳信息，支持群聊/私聊"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "需要戳一戳的用户id",
                    }
                },
                "required": ["uid"],
            },
            func=self._generate_poke_msg,
        )

    async def _generate_poke_msg(self, uid: str, session) -> str:
        if not uid.strip():
            raise ValueError("uid cannot be empty")
        scene = session.scene
        bot = nonebot.get_bot()
        try:
            await bot.call_api("poke", qq=uid)
        except Exception:
            try:
                if scene.is_group:
                    gid = scene.id
                    await bot.call_api(
                        "group_poke", user_id=uid, group_id=gid
                        )
                else:
                    await bot.call_api(
                        "friend_poke", user_id=uid
                        )
            except Exception:
                logger.warning(
                    "戳一戳发送失败，可能是协议端不支持...",
                    "[zhipu_toolkit][tool]戳一戳",
                    session=session,
                )
                return "戳一戳发送失败，可能是协议端不支持..."
        return "已成功发送戳一戳消息"
