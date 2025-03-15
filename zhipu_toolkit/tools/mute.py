import random

from nonebot import get_bot

from zhenxun.utils.platform import PlatformUtils
from zhenxun.utils.rules import ensure_group

from ._model import Tool


class MuteTool(Tool):
    def __init__(self):
        super().__init__(
            name="mute",
            description="用于禁言用户",
            parameters={
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "需要禁言的对象，为空则禁言对话者",
                    },
                    "minute": {
                        "type": "integer",
                        "description": "禁言时长，单位为分钟，默认为随机",
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
    def __init__(self):
        super().__init__(
            name="unmute",
            description="取消禁言对话者或指定的用户uin",
            parameters={
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "需要取消禁言的对象，为空则取消禁言对话者",
                    }
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
