from nonebot_plugin_alconna import Image, Target, UniMessage

from zhenxun.utils.rules import ensure_group

from ._model import Tool


class ImageSendTool(Tool):
    """网络图片发送工具"""

    def __init__(self):
        super().__init__(
            name="send_image",
            description=(
                "通过URL发送图片给用户。传入图片的url，返回发送结果（成功/失败原因）"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "图片的URL地址",
                    },
                },
                "required": ["url"],
            },
            func=self.send_image,
        )

    async def send_image(self, session, url: str) -> str:
        gid = session.scene.id
        uid = session.user.id
        if not ensure_group(session):
            private = True
            id_ = uid
        else:
            id_ = gid
            private = False
        target = Target(id_, private=private, self_id=session.self_id)
        try:
            await UniMessage(Image(url=url)).send(target=target)
            return "发送成功"
        except Exception as e:
            return f"发送失败: {e!s}"
