from nonebot_plugin_alconna import At, UniMessage

from ._model import Tool


class SpanAtMsg(Tool):
    """工具类：用于在消息中@指定用户"""

    def __init__(self):
        super().__init__(
            name="at_user",
            description=(
                "用于@指定用户UID，"
                "用于在消息中精准@指定用户"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "需要@的用户唯一标识符（UID）",
                    }
                },
                "required": ["uid"],
            },
            func=self._generate_at_msg,
        )

    async def _generate_at_msg(self, uid: str) -> str:
        if not uid.strip():
            raise ValueError("uid cannot be empty")
        await UniMessage(At("user", uid)).send()
        return "已成功发送@消息"
