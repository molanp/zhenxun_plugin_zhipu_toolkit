import asyncio
import datetime
import os
import random
from typing import ClassVar
import uuid

from nonebot.adapters.onebot.v11 import Event, MessageSegment
from nonebot_plugin_alconna import Text, Video
from zhipuai import ZhipuAI

from zhenxun.configs.config import BotConfig
from zhenxun.configs.path_config import IMAGE_PATH

from .config import ChatConfig


async def submit_task_to_zhipuai(message: str):
    client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
    return client.videos.generations(
        model=ChatConfig.get("VIDEO_MODEL"),
        prompt=message,
        with_audio=True,
    )


async def hello() -> list:
    """一些打招呼的内容"""
    result = random.choice(
        [
            "哦豁？！",
            "你好！Ov<",
            f"库库库，呼唤{BotConfig.self_nickname}做什么呢",
            "我在呢！",
            "呼呼，叫俺干嘛",
        ]
    )
    img = random.choice(os.listdir(IMAGE_PATH / "zai"))
    return [result, IMAGE_PATH / "zai" / img]


async def check_task_status_periodically(task_id: str, action):
    while True:
        try:
            response = await check_task_status_from_zhipuai(task_id)
        except Exception as e:
            await action.send(Text(str(e)), reply_to=True)
            break
        else:
            if response.task_status == "SUCCESS":
                await action.send(Video(url=response.video_result[0].url))
                break
            elif response.task_status == "FAIL":
                await action.send(Text("生成失败了.: ."), reply_to=True)
                break
            await asyncio.sleep(2)


async def check_task_status_from_zhipuai(task_id: str):
    client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
    return client.videos.retrieve_videos_result(id=task_id)


class ChatManager:
    chat_history: ClassVar[dict] = {}
    chat_history_token: ClassVar[dict] = {}

    @classmethod
    async def check_token(cls, uid: str, token_len: int):
        return  # 暂时没用，文档似乎说是单条token最大4095
        # if cls.chat_history_token.get(uid) is None:
        #     cls.chat_history_token[uid] = 0
        # cls.chat_history_token[uid] += token_len

        # user_history = cls.chat_history.get(uid, [])
        # while cls.chat_history_token[uid] > 4095 and len(user_history) > 1:
        #     removed_token_len = len(user_history[1]["content"])
        #     user_history = user_history[1:]
        #     cls.chat_history_token[uid] -= removed_token_len

        # cls.chat_history[uid] = user_history

    @classmethod
    async def send_message(cls, event: Event) -> list[MessageSegment]:
        # sourcery skip: use-fstring-for-formatting
        match ChatConfig.get("CHAT_MODE"):
            case "user":
                uid = str(event.sender.user_id)  # type: ignore
            case "group":
                uid = (
                    str(event.group_id)  # type: ignore
                    if hasattr(event, "group_id")
                    else str(event.sender.user_id)  # type: ignore
                )
            case "all":
                uid = "mix_mode"
            case _:
                raise ValueError("CHAT_MODE must be 'user', 'group' or 'all'")
        user_name = (
            event.sender.card  # type: ignore
            if hasattr(event.sender, "card") and event.sender.card  # type: ignore
            else event.sender.nickname  # type: ignore
        )
        message = ""
        for segment in event.get_message():
            if segment.type == "text":
                message += segment.data["text"]
            elif segment.type == "image":
                message += "[图片,描述:{}]".format(
                    await cls.__generate_image_description(
                        segment.data["url"].replace("https://", "http://")
                    )
                )
        if message.strip() == "":
            result = await hello()
            return [MessageSegment.text(result[0]), MessageSegment.image(result[1])]
        words = "现在时间是{}，我的名字是'{}'。{}".format(
            datetime.datetime.fromtimestamp(event.time).strftime("%Y-%m-%d %H:%M:%S"),
            user_name,
            message,
        )
        if len(words) > 4095:
            return [MessageSegment.text("超出最大token限制: 4095")]
        await cls.add_message(words, uid)
        loop = asyncio.get_event_loop()
        client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=ChatConfig.get("CHAT_MODEL"),
                    messages=cls.chat_history[uid],
                    user_id=uid,
                ),
            )
        except Exception as e:
            return [
                MessageSegment.text(
                    f"Error: {e!s}" + "\n\n如需清理对话记录，请发送'清理我的会话'"
                )
            ]
        result = response.choices[0].message.content  # type: ignore
        assert isinstance(result, str)
        await cls.add_message(result, uid, role="assistant")
        return [MessageSegment.text(result)]

    @classmethod
    async def add_message(cls, words: str, uid: str, role="user"):
        if cls.chat_history.get(uid) is None:
            cls.chat_history[uid] = [
                {"role": "system", "content": ChatConfig.get("SOUL")}
            ]
        cls.chat_history[uid].append({"role": role, "content": words})
        await cls.check_token(uid, len(words))

    @classmethod
    async def clear_history(cls, uid: str | None = None):
        if uid is None:
            count = len(cls.chat_history)
            cls.chat_history = {}
        elif cls.chat_history.get(uid) is None:
            count = 0
        else:
            count = len(cls.chat_history[uid])
            del cls.chat_history[uid]
        return count

    @classmethod
    async def __generate_image_description(cls, url):
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
        except Exception as e:
            result = str(e)
        assert isinstance(result, str)
        return result
