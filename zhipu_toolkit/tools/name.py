from nonebot import get_bot

from zhenxun.utils.rules import ensure_group

from ._model import Tool


class SetNameTool(Tool):
    def __init__(self):
        super().__init__(
            name="set_user_nickname",
            description="设置指定用户的群昵称",
            parameters={
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "用户uid",
                    },
                    "name": {
                        "type": "string",
                        "description": "用户群昵称",
                    },
                },
                "required": ["uin", "name"],
            },
            func=self.SetName,
        )

    async def SetName(self, session, uid: str, name: str) -> str:
        if not ensure_group(session):
            return "不是群组环境，不能设置群昵称"
        gid = session.scene.id
        uid = str(uid or session.user.id)
        bot = get_bot(self_id=session.self_id)

        try:
            await bot.set_group_card(group_id=gid, user_id=uid, card=name)
            return "设置成功"
        except Exception as e:
            return f"设置失败, 原因: {e!s}"
