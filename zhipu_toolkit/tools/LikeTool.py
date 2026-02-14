from nonebot import get_bot

from .AbstractTool import AbstractTool


class LikeTool(AbstractTool):
    name = "likeTool"
    description = "用户请求点赞相关的操作，包括给他人点赞或请求他人给自己点赞"
    parameters = {  # noqa: RUF012
        "type": "object",
        "properties": {
            "uid": {
                "type": "string",
                "description": "目标用户id。留空则使用发送者id",
            },
            "count": {
                "type": "number",
                "description": "点赞次数(最多20次)",
                "default": 10,
                "minimum": 1,
                "maximum": 20,
            },
        },
    }

    async def func(self, session, uid: str = "", count: int = 10) -> str:
        MAX_LIKES = 20
        actualCount = min(count, MAX_LIKES)
        try:
            targetQQ = uid or session.user.id
            targetQQNum = int(targetQQ)
            bot = get_bot(session.self_id)  # pyright: ignore[reportAssignmentType]
            result = await bot.send_like(user_id=targetQQNum, times=actualCount)
            assert isinstance(result, dict)
            return (
                f"点赞用户 {uid} 成功"
                if result["retcode"] == 0
                else f"点赞用户 {uid} 失败：{result['msg']}"
            )
        except Exception as e:
            return f"点赞用户 {uid} 失败：{e}"
