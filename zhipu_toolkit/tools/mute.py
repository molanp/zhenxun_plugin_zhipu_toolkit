import random

from nonebot import get_bot

from zhenxun.utils.platform import PlatformUtils

from .AbstractTool import AbstractTool


class MuteTool(AbstractTool):
    """禁言用户的工具（支持随机时长）"""

    def __init__(self):
        super().__init__(
            name="mute",
            description=(
                "禁言指定用户或对话者，支持自定义禁言时长（分钟）或随机1-100分钟，"
                "返回操作结果（成功/失败原因）。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "qq": {
                        "type": "string",
                        "description": "目标用户qq，留空则禁言当前用户",
                    },
                    "minute": {
                        "type": "number",
                        "description": "禁言时长（分钟），不填则随机1-100分钟",
                    },
                },
                "required": [],
            },
        )

    async def func(
        self, session, uid: str | None = None, minute: int | None = None
    ) -> str:
        bot = get_bot(self_id=session.self_id)
        gid = session.scene.id
        uid = str(uid or session.user.id)

        mute_time = minute or random.randint(1, 100)
        try:
            await PlatformUtils.ban_user(bot, uid, gid, mute_time)
            return f"禁言用户成功, 禁言时长: {mute_time}分钟"
        except Exception as e:
            return f"禁言用户失败, 原因: {e!s}"


class UnMuteTool(AbstractTool):
    """取消用户禁言的工具"""

    def __init__(self):
        super().__init__(
            name="unmute",
            description="取消指定用户或对话者的禁言状态，返回操作结果（成功/失败原因）。",
            parameters={
                "type": "object",
                "properties": {
                    "qq": {
                        "type": "string",
                        "description": "目标用户qq，留空则取消当前用户的禁言",
                    },
                },
                "required": [],
            },
        )

    async def func(self, session, uid: str | None = None) -> str:
        bot = get_bot(self_id=session.self_id)
        gid = session.scene.id
        uid = str(uid or session.user.id)
        try:
            await PlatformUtils.ban_user(bot, uid, gid, 0)
            return "取消禁言用户成功"
        except Exception as e:
            return f"取消禁言用户失败, 原因: {e!s}"
