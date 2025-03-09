import random

from nonebot import get_bot

from zhenxun.utils.rules import ensure_group

from ._model import Tool


class MuteTool(Tool):
    def __init__(self):
        super().__init__(
            name="mute",
            description="禁言对话者或指定的用户uin",
            parameters={
                "type": "object",
                "properties": {
                    "uin": {
                        "type": "integer",
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

    async def Mute(self, session, uin: int | None = None, minute: int | None = None) -> str:
        if not ensure_group(session):
            return "不是群组环境，不能禁言"
        bot = get_bot(self_id=session.self_id)
        gid = session.scene.id
        uid = uin or session.user.id
        try:
            member_info = await bot.get_group_member_info(
                group_id=gid, user_id=bot.self_id
            )
            bot_role = member_info["role"]
        except Exception:
            return "获取成员信息失败"

        try:
            sender_info = await bot.get_group_member_info(group_id=gid, user_id=uid)
            sender_role = sender_info["role"]
        except Exception:
            return "获取成员信息失败"

        if bot_role not in ["admin", "owner"]:
            return "不是管理员，不能禁言"
        if bot_role == "admin" and sender_role in ["owner", "admin"]:
            return "不能禁言对方"

        mute_time = minute or random.randint(1, 100)
        try:
            await bot.set_group_ban(
                group_id=gid,
                user_id=uid,
                duration=mute_time * 60,
            )
            return f"已禁言 {uid} {mute_time} 分钟"
        except Exception:
            return "禁言失败"
