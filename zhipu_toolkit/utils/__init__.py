import asyncio
import base64
import datetime
import re
import uuid

from nonebot import get_bot, require

from zhenxun.utils.http_utils import AsyncHttpx

require("nonebot_plugin_alconna")
require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import At, Image, Text, UniMessage
from nonebot_plugin_uninfo import Session, Uninfo
from zai import ZhipuAiClient as ZhipuAI

from zhenxun.utils.platform import PlatformUtils

from ..config import ChatConfig


def get_request_id() -> str:
    """
    获取请求ID。

    返回:
    str: 请求ID。
    """
    return str(uuid.uuid4())


async def msg2str(
    msg: UniMessage, is_multimodal: bool = False
) -> tuple[str, str | None]:
    message = ""
    res = None
    for segment in msg:
        if isinstance(segment, At):
            message += f"@[qq={segment.target}] "
        elif isinstance(segment, Image):
            assert segment.url is not None
            img_url = segment.url.replace("https://", "http://")
            if is_multimodal:
                res = base64.b64encode(await AsyncHttpx.get_content(img_url)).decode()
            else:
                message += (
                    f"\n![图片内容:{await generate_image_description(img_url)}]"
                    f"({img_url})"
                )
        elif isinstance(segment, Text):
            message += segment.text
        else:
            message += str(segment).replace("[reply]", "\n")
    return message, res


def str2msg(message: str) -> list[Text]:
    """
    将字符串消息转换为消息段列表。

    该函数解析输入的字符串消息，将其中的 `@` 转换为对应的消息段，并将文本分割成每句话。

    :param message: 输入的字符串消息。
    :return: 包含消息段的列表，每个消息段为 MessageSegment 实例。
    """
    segments = []
    at_pattern = r"@UID ([^ ]+)|@\[uid=([^>]+)\]"
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


def get_username_by_session(session: Session) -> str:
    if (
        hasattr(session.member, "nick")
        and session.member is not None
        and session.member.nick != ""
        and session.member.nick is not None
    ):
        name = session.member.nick
    else:
        name = session.user.name
    if name is None:
        return "未知用户"
    return re.sub(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]", "", name) or "未知用户"


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


async def split_text(text: str) -> list[tuple[list[Text], float]]:
    """文本切割"""
    results = []
    max_split = ChatConfig.get("TEXT_MAX_SPLIT")
    split_list = (
        [s for s in await __split_text(text, r"[。？！\n]+", max_split) if s.strip()]
        if max_split > -1
        else [text]
    )

    if not split_list and text.strip():
        split_list = [text]

    for r in split_list:
        next_char_index = text.find(r) + len(r)
        while next_char_index < len(text) and text[next_char_index] == "？":
            r += "？"
            next_char_index += 1
        results.append((str2msg(r), min(len(r) * 0.2, 3.0)))

    return results


def format_usr_msg(username: str, session: Uninfo, msg: str) -> str:
    """\n"""
    return (
        "<META_DATA>\n"
        f"当前时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"对话者昵称: {username}\n"
        f"对话者UID: {session.user.id}\n"
        "</META_DATA>\n"
        f"{msg}"
    )


def extract_message_content(msg: str | None, to_msg: bool = False) -> str | list[Text]:
    """
    从格式化的消息中提取实际的消息内容

    参数:

    - msg (str): 格式化的消息字符串。
    - to_msg (bool): 是否直接转换为msg对象

    返回:

    - str: 提取的实际消息内容。
    """
    if msg is None:
        return ""
    # 去除开头的空白字符，包括换行符
    msg = msg.lstrip()
    pattern = re.compile(
        r"^.*?"  # 匹配昵称开头
        r"(?:\([^)]+\))?"  # 匹配括号内的任意内容（直到右括号）
        r"[:：]\s*"  # 匹配冒号及空格
        r"(?P<message>.*)$",  # 捕获消息内容
        re.DOTALL,
    )
    match = pattern.match(msg.strip())
    message = match["message"].strip() if match else msg.strip()
    message = message.rstrip("。")
    return str2msg(message) if to_msg else message


async def get_username(bot_id: str, uid: str, group_id: str | None = None) -> str:
    bot = get_bot(bot_id)
    info = await PlatformUtils.get_user(bot, uid, group_id)
    if info is None:
        return "未知用户"
    name = info.card or info.name
    return re.sub(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]", "", name)
