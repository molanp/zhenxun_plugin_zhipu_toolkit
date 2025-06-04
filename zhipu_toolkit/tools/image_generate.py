from nonebot_plugin_alconna import Image, Target, UniMessage
from zhenxun.utils.rules import ensure_group
from zhipuai import ZhipuAI
from ._model import Tool
from ..config import ChatConfig
import asyncio


class ImageGenTool(Tool):
    """图片生成工具"""

    def __init__(self):
        super().__init__(
            name="image_generate",
            description="通过文本生成图片并发送给用户(需要等待30秒左右)",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "要生成图片的内容",
                    },
                    "size": {
                        "type": "string",
                        "description": "生成图片的像素尺寸.需满足长宽都在512px-2048px之间 , 且为16整数倍,例如`1440x960`"
                    }
                },
                "required": ["prompt"],
            },
            func=self.image_gen,
        )

    async def image_gen(self, session, prompt: str, size:  str = "1440x960") -> str:
        gid = session.scene.id
        uid = session.user.id
        if not ensure_group(session):
            private = True
            id_ = uid
        else:
            id_ = gid
            private = False
        target = Target(id_, private=private, self_id=session.self_id)
        client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
        try:
            response = await asyncio.to_thread(
                client.images.generations,
                model=ChatConfig.get("PIC_MODEL"),
                prompt=prompt,
                size=size,
            )
            await UniMessage(Image(url=response.data[0].url)).send(target=target)
            return "发送成功"
        except Exception as e:
            return f"错误: {e!s}"
