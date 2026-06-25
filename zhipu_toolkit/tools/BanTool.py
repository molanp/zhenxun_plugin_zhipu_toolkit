import random

from zhenxun.models.ban_console import BanConsole
from nonebot_plugin_uninfo import Uninfo

from .AbstractTool import AbstractTool


class BanTool(AbstractTool):
    """拉黑用户的工具"""

    name = "banTool"
    description = (
        "安全防御工具。当发现当前用户正在连续发送高度重复的废话、恶意刷屏、"
        "或通过高频无意义信息进行垃圾信息轰炸时，"
        "你必须立即调用此工具对该用户进行封禁惩罚。日常正常交流或有意义的提问严禁调用。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "封禁原因。必须写明触发防御的具体表现，例如用户连续重复无意义内容或高频恶意刷屏。",
            },
            "minute": {
                "type": "number",
                "description": (
                    "拉黑时长，单位为分钟。你必须根据当前用户的恶劣程度自主决定封禁时间。"
                    "情节严重或屡教不改者，建议直接填写 1440（1天）、10080（7天）或 43200（30天）以示严惩；"
                    "只有在用户只是轻微刷屏且你想给予随机轻微惩罚时，才允许将此项留空。"
                ),
            },
        },
        "required": ["reason"],
    }

    async def func(
        self,
        session: Uninfo,
        reason: str = "",
        minute: int | None = None,
    ) -> str:
        uid = session.user.id
        ban_time = minute or random.randint(1, 100)
        try:
            await BanConsole.ban(
                uid,
                None,
                9999,
                reason,
                ban_time * 60,
            )
            return (
                f"success: bad_user_{uid}_has_been_blocked_and_banned_for_{ban_time}_minutes. "
                f"security_defense_activated. reason: {reason}"
            )
        except Exception as e:
            return f"error: security_defense_failed_to_ban_user_{uid}, exception: {e!s}"


class UnBanTool(AbstractTool):
    """取消拉黑用户的工具"""

    name = "unbanTool"
    description = "高危管理操作工具。仅在收到明确帮他人解除拉黑的指令，且对话中清晰给出了具体用户id时调用。日常闲聊绝对禁止调用。"
    parameters = {
        "type": "object",
        "properties": {
            "uid": {
                "type": "number",
                "description": "需要解封的目标用户id。必须从用户指令中准确提取具体数字，严禁留空或胡编乱造。",
            },
        },
        "required": ["uid"],
    }

    async def func(self, uid: str) -> str:
        if await BanConsole.unban(uid):
            return f"success: user_{uid}_has_been_unbanned"
        else:
            return f"error: user_{uid}_not_in_black_list"
