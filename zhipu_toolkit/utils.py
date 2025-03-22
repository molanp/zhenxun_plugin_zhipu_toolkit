import asyncio
import datetime
from pathlib import Path
import re
import shutil
import uuid

from nonebot_plugin_alconna import At, Image, Text, UniMsg
from nonebot_plugin_uninfo import Session, Uninfo
import ujson
from zhipuai import ZhipuAI

from zhenxun.services.log import logger
from zhenxun.configs.config import BotConfig

from .config import ChatConfig
from .model import ZhipuChatHistory


async def get_request_id() -> str:
    """
    获取请求ID。

    返回:
    str: 请求ID。
    """
    return str(uuid.uuid4())


async def msg2str(msg: UniMsg) -> str:
    message = ""
    for segment in msg:
        if isinstance(segment, At):
            message += f"@[uid={segment.target}] "
        elif isinstance(segment, Image):
            assert segment.url is not None
            url = segment.url.replace(
                "https://multimedia.nt.qq.com.cn", "http://multimedia.nt.qq.com.cn"
            )
            message += f"\n![{await generate_image_description(url)}]({url})"
        elif isinstance(segment, Text):
            message += segment.text
    return message


async def str2msg(message: str) -> list:
    """
    将字符串消息转换为消息段列表。

    该函数解析输入的字符串消息，将其中的 `@` 转换为对应的消息段，并将文本分割成每句话。

    :param message: 输入的字符串消息。
    :return: 包含消息段的列表，每个消息段为 MessageSegment 实例。
    """
    segments = []
    message = message.removesuffix("。")
    at_pattern = r"@UID ([^ ]+)|@<uid=([^>]+)>"
    last_pos = 0

    for match in re.finditer(at_pattern, message, re.DOTALL):
        if match.start() > last_pos:
            segments.append(Text(message[last_pos : match.start()]))
        uid = match.group(1) or match.group(2)
        segments.append(At("user", uid))
        last_pos = match.end()
    if last_pos < len(message):
        segments.append(Text(message[last_pos:]))

    return segments


async def get_user_nickname(session: Session) -> str:
    if (
        hasattr(session.member, "nick")
        and session.member is not None
        and session.member.nick != ""
        and session.member.nick is not None
    ):
        return session.member.nick
    return session.user.name if session.user.name is not None else "未知"


async def generate_image_description(url: str):
    loop = asyncio.get_event_loop()
    client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
    try:
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=ChatConfig.get("IMAGE_UNDERSTANDING_MODEL"),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "描述图片"},
                            {
                                "type": "image_url",
                                "image_url": {"url": url},
                            },
                        ],
                    }
                ],
                user_id=str(uuid.uuid4()),
            ),
        )
        result = response.choices[0].message.content  # type: ignore
    except Exception:
        result = ""
    assert isinstance(result, str)
    return result.replace("\n", "\\n")


async def __split_text(text: str, pattern: str, maxsplit: int) -> list[str]:
    """辅助函数，用于分割文本"""
    return re.split(pattern, text, maxsplit)


async def split_text(text: str) -> list[tuple[str, float]]:
    """文本切割"""
    results = []
    split_list = [
        s for s in await __split_text(text, r"(?<!\?)[。？！\n](?!\?)", 3) if s.strip()
    ]
    for r in split_list:
        next_char_index = text.find(r) + len(r)
        if next_char_index < len(text) and text[next_char_index] == "？":
            r += "？"
        results.append((await str2msg(r), min(len(r) * 0.2, 3.0)))
    return results


async def remove_directory_with_retry(
    path: Path, retries: int = 3, delay: float = 0.5
) -> None:
    for attempt in range(retries):
        try:
            shutil.rmtree(path)
            return
        except Exception as e:
            if attempt == retries - 1:
                logger.error(
                    "Failed to remove directory after multiple attempts",
                    "zhipu_toolkit",
                    e=e,
                )
            else:
                await asyncio.sleep(delay)


async def migrate_user_data(uid: str, messages: list[dict]) -> bool:
    try:
        valid_messages = [
            msg for msg in messages if isinstance(msg, dict) and "role" in msg
        ]
        await ZhipuChatHistory.bulk_create(
            [ZhipuChatHistory(uid=uid, **msg) for msg in valid_messages]
        )
        return True
    except Exception as e:
        logger.error(f"UID {uid} 迁移对话数据失败", "zhipu_toolkit", e=e)
        return False


async def format_usr_msg(nickname: str, session: Uninfo, msg: str) -> str:
    """\n"""
    data = {
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "nickname": nickname,
        "uid": session.user.id,
        "message": msg,
    }
    return ujson.dumps(data, ensure_ascii=False)


async def extract_message_content(msg: str) -> str:
    """
    从格式化的消息中提取实际的消息内容。
    参数:
    - msg (str): 格式化的消息字符串。
    返回:
    - str: 提取的实际消息内容。
    """
    pattern = re.compile(
        rf"^{re.escape(BotConfig.self_nickname)}"  # 匹配昵称开头
        rf"(?:\([^)]+\))?"  # 修改：匹配括号内的任意内容（直到右括号）
        rf"[:：]\s*"  # 匹配冒号及空格
        rf"(?P<message>.*)$",  # 捕获消息内容
        re.DOTALL,
    )
    match = pattern.match(msg)
    return match["message"].strip() if match else msg.strip()


async def get_answer(answer: str | None) -> str | None:
    if answer is None:
        return None
    try:
        data = ujson.loads(str(answer).strip())["answer"]
    except (ujson.JSONDecodeError, KeyError):
        data = str(answer).strip()
    data = data.replace("\\n", "\n").replace("\\t", "\t")
    if not data:
        return None
    return await extract_message_content(data)
