import random

from nonebot import get_bot

from zhenxun.utils.rules import ensure_group

from ._model import Tool


class MuteTool(Tool):
    def __init__(self):
        super().__init__(
            name="mute",
            description="禁言对话者或指定uid",
            parameters={
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "需要禁言的对象，为空则禁言对话者",
                    }
                },
                "required": [],
            },
            func=self.Mute,
        )

    async def Mute(self, session, uid: str | None = None) -> str:
        if not ensure_group(session):
            return "不是群组环境，不能禁言"
        bot = get_bot(self_id=session.self_id)
        gid = session.scene.id
        uid = uid or session.user.id
        try:
            member_info = await bot.get_group_member_info(
                group_id=gid, user_id=bot.self_id
            )
            if member_info["role"] not in ["admin", "owner"]:
                return "不是管理员，不能禁言"
        except Exception:
            return "禁言失败"

        try:
            sender_info = await bot.get_group_member_info(
                group_id=gid, user_id=uid
            )
            if sender_info["role"] in ["admin", "owner"]:
                return "不能禁言管理员"
        except Exception:
            return "禁言失败"

        mute_time = random.randint(1, 100)
        try:
            await bot.set_group_ban(
                group_id=gid,
                user_id=uid,
                duration=mute_time * 60,
            )
            return f"已禁言 {uid} {mute_time} 分钟"
        except Exception:
            return "禁言失败"
