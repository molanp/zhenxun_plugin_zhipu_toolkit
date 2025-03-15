from nonebot_plugin_alconna import Image, Target, UniMessage

from ._model import Tool


class ImageSendTool(Tool):
    def __init__(self):
        super().__init__(
            name="send_image",
            description="用于向用户发送一张网络图片",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "图片url",
                    },
                },
                "required": ["url"],
            },
            func=self.send_image,
        )

    async def send_image(self, session, url: str) -> str:
        gid = session.scene.id
        uid = session.user.id
        if not gid:
            private = True
            id_ = uid
        else:
            id_ = gid
            private = False
        target = Target(id=id_, private=private, self_id=session.self_id)
        try:
            await UniMessage(Image(url=url)).send(target=target)
            return "发送成功"
        except Exception as e:
            return f"发送失败: {e!s}"
