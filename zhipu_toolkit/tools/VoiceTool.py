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
    """发送语音回复的工具"""

    name = "voiceTool"
    description = (
        "安全与合规工具。日常普通对话、信息查询、闲聊开玩笑绝对禁止调用此工具，必须直接文本回复。\n"
        "仅在当前用户明确发出“发语音”、“语音回复我”、“想听你的声音”等纯语音功能请求时，才允许调用此工具。\n"
        "同时，为了防止语音合成资源被恶意消耗，转换的文本内容必须精简，严禁长篇大论。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "需要转为语音的纯文本内容。严禁包含任何颜文字、Emoji表情或特殊符号。"
                    "如果文本中包含任何英文单词、字母或简称，你必须在生成时将其彻底替换为流畅的中文发音谐音"
                    "（例如：将“AI”替换为“爱哎”，将“OK”替换为“欧克”，将“QQ”替换为“扣扣”），否则语音合成会失败。"
                ),
            }
        },
        "required": ["text"],
    }

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
                return f"success: voice_sent_successfully, user_will_hear_text: {text}, has_already_been_sent_by_system: true"
            else:
                return "发送语音失败"
        except Exception as e:
            logger.error(
                "发送语音失败", "zhipu_toolkit.tools.voice", session=session, e=e
            )
            return f"error: voice_dispatch_failed, exception: {e!s}"
