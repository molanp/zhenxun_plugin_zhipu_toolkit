import random

from nonebot import get_bot

from zhenxun.models.level_user import LevelUser
from zhenxun.utils.platform import PlatformUtils
from zhenxun.utils.rules import ensure_group

from .AbstractTool import AbstractTool


class MuteTool(AbstractTool):
    """禁言用户的工具（支持随机时长）"""

    name = "muteTool"
    description = (
        "禁言指定用户或对话者，支持自定义禁言时长（分钟）或随机1-100分钟，"
        "返回操作结果（成功/失败原因）。"
    )
    parameters = {  # noqa: RUF012
        "type": "object",
        "properties": {
            "uid": {
                "type": "number",
                "description": "目标用户id，留空则禁言当前用户",
            },
            "minute": {
                "type": "number",
                "description": "禁言时长（分钟），不填则随机1-100分钟",
                "minimum": 1,
                "maximum": 43200,
            },
        },
        "required": [],
    }

    async def func(
        self, session, uid: str | None = None, minute: int | None = None
    ) -> str:
        if not ensure_group(session):
            return "不是群聊环境，不能执行此操作"
        bot = get_bot(self_id=session.self_id)
        gid = session.scene.id
        uid = str(uid or session.user.id)
        level = await LevelUser.get_user_level(session.user.id, gid)
        if level < 5 and uid != session.user.id:
            return "用户权限不足，不能执行此操作"

        mute_time = minute or random.randint(1, 100)
        try:
            await PlatformUtils.ban_user(bot, uid, gid, mute_time)
            return f"禁言用户{uid}, {mute_time} 分钟成功"
        except Exception:
            return f"失败了，我在这个群聊 {gid} 没有权限禁言别人"


class UnMuteTool(AbstractTool):
    """取消用户禁言的工具"""

    name = "unmute"
    description = "取消指定用户或对话者的禁言状态，返回操作结果（成功/失败原因）。"
    parameters = {  # noqa: RUF012
        "type": "object",
        "properties": {
            "uid": {
                "type": "number",
                "description": "目标用户id，留空则取消当前用户的禁言",
            },
        },
        "required": [],
    }

    async def func(self, session, uid: str | None = None) -> str:
        if not ensure_group(session):
            return "不是群聊环境，不能执行此操作"
        bot = get_bot(self_id=session.self_id)
        gid = session.scene.id
        uid = str(uid or session.user.id)
        level = await LevelUser.get_user_level(session.user.id, gid)
        if level < 5 and uid != session.user.id:
            return "用户权限不足，不能执行此操作"
        try:
            await PlatformUtils.ban_user(bot, uid, gid, 0)
            return f"取消禁言用户{uid} 成功"
        except Exception:
            return f"失败了，我在这个群聊 {gid} 没有权限解禁别人"
