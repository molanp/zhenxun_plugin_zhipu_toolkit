import random
import string

from nonebot_plugin_alconna import Target, UniMessage, Voice
from nonebot_plugin_uninfo import Uninfo

from zhenxun.services.log import logger
from zhenxun.utils.http_utils import AsyncHttpx
from zhenxun.utils.rules import ensure_group

from .AbstractTool import AbstractTool


def random_str():
    """生成11位随机字符串"""
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(11))


class VoiceTool(AbstractTool):
    def __init__(self):
        super().__init__(
            name="voiceTool",
            description=(
                "这是一个实现你发送语音功能的工具，平常正常对话时、当你想发送语音时，调用此工具。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": (
                            "你想发送的语音文字(注意不要包含颜文字等内容，"
                            "只要纯文字，颜文字等内容会使语音转文字出问题，如果有英文单词或字母尝试用中文谐音代替)"
                        ),
                    }
                },
                "required": ["text"],
            },
        )

    async def func(self, session: Uninfo, text: str) -> str:
        if not text.strip():
            raise ValueError("text cannot be empty")
        if ensure_group(session):
            target = Target(session.scene.id)
        else:
            target = Target(session.user.id, private=True)
        file = "https://www.modelscope.cn/api/v1/studio/Xzkong/AI-jiaran/gradio/file="
        ck = (
            "session=MTc1MjY0NzczOXxEWDhFQVFMX2dBQUJFQUVRQUFEX3hmLUFB"
            "QVlHYzNSeWFXNW5EQVFBQW1sa0EybHVkQVFFQVA0S0ZnWnpkSEpwYm1jT"
            "UNnQUlkWE5sY201aGJXVUdjM1J5YVc1bkRCRUFELVdHc09XSGllV0lzT21B"
            "bXVtQWp3WnpkSEpwYm1jTUJnQUVjbTlzWlFOcGJuUUVBZ0FDQm5OMGNtbHVad"
            "3dJQUFaemRHRjBkWE1EYVc1MEJBSUFBZ1p6ZEhKcGJtY01Cd0FGYkdWMlpXd0dj"
            "M1J5YVc1bkRBZ0FCbFJwWlhJZ01RWnpkSEpwYm1jTUVRQVBjMlZ6YzJsdmJsOTJaW"
            "Ep6YVc5dUJXbHVkRFkwQkFvQS1EQ2xUNnFCMzJHb3y5H0YUVdJyT50SZGYpSgHz20sqNKQPWKoeTmOYl7AOvA=="
        )
        try:
            result = await AsyncHttpx.post(
                "https://www.modelscope.cn/api/v1/studio/Xzkong/AI-jiaran/gradio/run/predict",
                json={
                    "data": [text, "jiaran", 0.2, 0.6, 0.8, 1],
                    "fn_index": 0,
                    "session_hash": random_str(),
                },
                cookies={"session": ck},
                timeout=120,
            )
            result = result.json()
            if result and result["data"][0] == "Success":
                file_url = result["data"][1]["name"]
            else:
                file_url = None
            voice = file + file_url if file_url else None
            if voice:
                await UniMessage(Voice(url=voice)).send(target=target)
                return (
                    f"发送语音内容({text})成功，你已经发送语音了，所以不需要强调你"
                    "已经发送语音，继续说之后的事情"
                )
            else:
                return "发送语音失败"
        except Exception as e:
            logger.error(
                "发送语音失败", "zhipu_toolkit.tools.voice", session=session, e=e
            )
            return f"发送语音失败: {e}"
