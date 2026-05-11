import asyncio
import base64
import datetime
import random
import re
import time
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
from nonebot.adapters.onebot.v11 import Bot
from zhenxun.services.log import logger

FACE_CACHE_LIST: tuple[list[str], float] = ([], 0.0)


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
            message += f"<AT user={segment.target}> "
        elif isinstance(segment, Image):
            assert segment.url is not None
            img_url = segment.url.replace("https://", "http://")
            if is_multimodal:
                res = base64.b64encode(await AsyncHttpx.get_content(img_url)).decode()
            else:
                message += f"\n![#image:{await generate_image_description(img_url)}]"
        elif isinstance(segment, Text):
            message += segment.text
        else:
            message += str(segment).replace("[reply]", "\n")
    return message, res


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


async def split_text(text: str) -> list[tuple[Text, float]]:
    """文本切割"""
    results: list[tuple[Text, float]] = []
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
        results.append((Text(r), min(len(r) * 0.2, 3.0)))

    return results


def format_usr_msg(username: str, session: Uninfo, msg: str) -> str:
    """\n"""
    return (
        "<META_DATA>\n"
        f"Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Name: {username}\n"
        f"Uid: {session.user.id}\n"
        "</META_DATA>\n"
        f"{msg}"
    )


def extract_message_content(msg: str | None) -> str:
    """
    从格式化的消息中提取实际的消息内容

    参数:

    - msg (str): 格式化的消息字符串。

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
    return message


async def get_username(bot_id: str, uid: str, group_id: str | None = None) -> str:
    bot = get_bot(bot_id)
    info = await PlatformUtils.get_user(bot, uid, group_id)
    if info is None:
        return "未知用户"
    name = info.card or info.name
    return re.sub(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]", "", name)


async def get_custom_face(bot: Bot):
    global FACE_CACHE_LIST
    if (time.time() - FACE_CACHE_LIST[1]) > 7200:
        try:
            FACE_CACHE_LIST = ((await bot.fetch_custom_face())["data"], time.time())
        except Exception as e:
            logger.error("获取QQ收藏表情失败", "zhipu_toolkit:get_custom_face", e=e)
            return ""
    if fcl := FACE_CACHE_LIST[0]:
        return random.choice(fcl)
    return ""


async def send_face(bot: Bot) -> UniMessage | None:
    if isinstance(bot, Bot):
        if fre := ChatConfig.get("FACE_SEND_FREQUENCY"):
            if random.random() * 100 < fre:
                if face := await get_custom_face(bot):
                    return UniMessage.image(url=face)
    return None
