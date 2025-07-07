import nonebot
from ._model import Tool
from nonebot_plugin_alconna import UniMessage, At

class PokeMsg(Tool):
    """工具类：用于戳一戳指定用户"""

    def __init__(self):
        super().__init__(
            name="poke_user",
            description=(
                "用于戳一戳指定用户"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "需要戳一戳的用户唯一标识符（UID）",
                    }
                },
                "required": ["uid"],
            },
            func=self._generate_poke_msg,
        )

    async def _generate_poke_msg(self, uid: str, session) -> str:
        scene = session.scene
        gid = scene.id if scene.is_group else None # 传入此参数按group_poke发送,否则按friend_poke发送
        bot = nonebot.get_bot()
        if not uid.strip():
            raise ValueError("uid cannot be empty")
        await bot.send_poke(group_id=gid, user_id=uid)
        return "已成功发送戳一戳消息"
