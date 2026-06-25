from nonebot import get_bot

from .AbstractTool import AbstractTool
from nonebot.adapters.onebot.v11 import ActionFailed
from nonebot_plugin_uninfo import Uninfo


class LikeTool(AbstractTool):
    name = "likeTool"
    description = (
        "防刷与合规工具。仅在用户明确发出帮他点赞、赞我、刷赞等特定功能指令时调用。"
        "当用户在日常闲聊中使用好赞、给你点赞、太赞了等口头禅或表达夸奖时，绝对禁止调用。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "uid": {
                "type": "string",
                "description": "需要点赞的目标用户id。如果用户是要求赞他自己（如赞我），此项必须留空。只有当用户明确提供了他人的数字id并要求帮他人点赞时，才填写具体id。",
            },
            "count": {
                "type": "number",
                "description": "点赞的具体次数。必须根据用户指令中的数字确定（最大允许20）。若用户未指定具体次数，此项必须留空以应用系统默认值。",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
        },
    }

    async def func(self, session: Uninfo, uid: str = "", count: int = 10) -> str:
        MAX_LIKES = 20
        actual_count = min(count, MAX_LIKES)
        target_qq = uid or session.user.id
        try:
            target_qq_num = int(target_qq)
            bot = get_bot(session.self_id)  # pyright: ignore[reportAssignmentType]
            try:
                await bot.send_like(user_id=target_qq_num, times=actual_count)
                is_self = "true" if target_qq == session.user.id else "false"
                return f"success: liked_user_{target_qq}_for_{actual_count}_times, is_self_request: {is_self}"
            except ActionFailed:
                return "error: platform_rejected, reason: 今日同一好友点赞数已达上限"

        except ValueError:
            return "error: invalid_uid_format (must be a valid qq number string)"
        except Exception as e:
            return f"error: execution_failed, exception: {e!s}"
