from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Bot
from nonebot_plugin_uninfo import Uninfo

from .AbstractTool import AbstractTool


class LikeTool(AbstractTool):
    def __init__(self):
        super().__init__(
            name="likeTool",
            description="用户请求点赞相关的操作，包括给他人点赞或请求他人给自己点赞",
            parameters={
                "type": "object",
                "properties": {
                    "qq": {
                        "type": "string",
                        "description": "目标用户QQ号。留空则使用发送者QQ",
                    },
                    "count": {
                        "type": "number",
                        "description": "点赞次数(最多20次)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
            },
        )

    async def func(self, session: Uninfo, qq: str = "", count: int = 10) -> str:
        MAX_LIKES = 20
        actualCount = min(count, MAX_LIKES)
        try:
            targetQQ = qq or session.user.id
            targetQQNum = int(targetQQ)
            bot: Bot = get_bot(session.self_id)  # pyright: ignore[reportAssignmentType]
            result = await bot.send_like(user_id=targetQQNum, times=actualCount)
            assert isinstance(result, dict)
            return (
                "点赞成功" if result["retcode"] == 0 else f"点赞失败：{result['msg']}"
            )
        except Exception as e:
            return f"点赞失败：{e}"
