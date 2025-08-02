import random

from zhenxun.models.ban_console import BanConsole
from ._model import Tool


class BanTool(Tool):
    """拉黑用户的工具（支持随机时长）"""

    def __init__(self):
        super().__init__(
            name="ban",
            description=(
                "拉黑指定用户或对话者，支持自定义拉黑时长（分钟）或随机1-100分钟，"
                "返回操作结果（成功/失败原因）。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "目标用户UID，留空则拉黑对话者",
                    },
                    "reason": {
                        "type": "string",
                        "description": "封禁该用户的原因"
                    },
                    "minute": {
                        "type": "integer",
                        "description": "拉黑时长（分钟），不填则随机1-100分钟",
                    },
                },
                "required": ["reason"],
            },
            func=self.Ban,
        )

    async def Ban(
        self, session, uid: str | None = None, reason: str = "", minute: int | None = None
    ) -> str:
        uid = str(uid or session.user.id)
        mute_time = minute or random.randint(1, 100)
        try:
            await BanConsole.ban(
                uid,
                None,
                9999,
                reason,
                mute_time * 60,
            )
            return f"拉黑用户成功, 拉黑时长: {mute_time}分钟"
        except Exception as e:
            return f"拉黑用户失败, 原因: {e!s}"


class UnBanTool(Tool):
    """取消拉黑用户的工具"""

    def __init__(self):
        super().__init__(
            name="unban",
            description="取消指定用户或对话者的拉黑状态，返回操作结果（成功/失败原因）。",
            parameters={
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "目标用户UID，留空则取消对话者的拉黑",
                    },
                },
                "required": [],
            },
            func=self.UnBan,
        )

    async def UnBan(self, session, uid: str | None = None) -> str:
        uid = str(uid or session.user.id)
        return "取消拉黑用户成功" if await BanConsole.unban(uid) else "取消拉黑用户失败: 该用户不在黑名单内"
