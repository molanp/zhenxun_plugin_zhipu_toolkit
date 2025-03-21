import random

from nonebot import get_bot

from zhenxun.utils.platform import PlatformUtils
from zhenxun.utils.rules import ensure_group

from ._model import Tool


class MuteTool(Tool):
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
                    "uid": {
                        "type": "string",
                        "description": "目标用户UID，留空则禁言指令发起者",
                    },
                    "minute": {
                        "type": "integer",
                        "description": "禁言时长（分钟），不填则随机1-100分钟",
                    },
                },
                "required": [],
            },
            func=self.Mute,
        )

    async def Mute(
        self, session, uid: str | None = None, minute: int | None = None
    ) -> str:
        if not ensure_group(session):
            return "不是群组环境，不能禁言"
        bot = get_bot(self_id=session.self_id)
        gid = session.scene.id
        uid = str(uid or session.user.id)

        mute_time = minute or random.randint(1, 100)
        try:
            await PlatformUtils.ban_user(bot, uid, gid, mute_time)
            return f"禁言成功, 禁言时长: {mute_time}分钟"
        except Exception as e:
            return f"禁言失败, 原因: {e!s}"


class UnMuteTool(Tool):
    """取消用户禁言的工具"""

    def __init__(self):
        super().__init__(
            name="unmute",
            description="取消指定用户或对话者的禁言状态，返回操作结果（成功/失败原因）。",
            parameters={
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "目标用户UID，留空则取消指令发起者的禁言",
                    },
                },
                "required": [],
            },
            func=self.UnMute,
        )

    async def UnMute(self, session, uid: str | None = None) -> str:
        if not ensure_group(session):
            return "不是群组环境，不能取消禁言"
        bot = get_bot(self_id=session.self_id)
        gid = session.scene.id
        uid = str(uid or session.user.id)
        try:
            await PlatformUtils.ban_user(bot, uid, gid, 0)
            return "取消禁言成功"
        except Exception as e:
            return f"取消禁言失败, 原因: {e!s}"
