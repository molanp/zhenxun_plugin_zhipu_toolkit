import asyncio
import datetime
import os
import random
from typing import ClassVar
import uuid

from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent, MessageSegment
from nonebot_plugin_alconna import Text, Video
from pydantic import BaseModel
from zhipuai import ZhipuAI

from zhenxun.configs.config import BotConfig
from zhenxun.services.log import logger
from zhenxun.configs.path_config import IMAGE_PATH

from .config import ChatConfig


class GroupMessageModel(BaseModel):
    uid: str
    nickname: str
    msg: str


GROUP_MSG_CACHE: dict[str, list[GroupMessageModel]] = {}


async def cache_group_message(event: GroupMessageEvent):
    msg = GroupMessageModel(
        uid=str(event.sender.user_id),
        nickname=await ChatManager.get_user_nickname(event),
        msg=await ChatManager.get_message(event),
    )

    gid = str(event.group_id)
    logger.debug(f"GROUP {gid} 成功缓存聊天记录: {msg[:100]}", "zhipu_toolkit")
    if gid in GROUP_MSG_CACHE:
        if len(GROUP_MSG_CACHE[gid]) >= 20:
            GROUP_MSG_CACHE[gid].pop(0)
            logger.debug(f"GROUP {gid} 缓存已满，自动清理最早的记录", "zhipu_toolkit")

        GROUP_MSG_CACHE[gid].append(msg)
    else:
        GROUP_MSG_CACHE[gid] = [msg]


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


async def check_task_status_periodically(task_id: str, action) -> None:
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
    impersonation_group: ClassVar[dict] = {}

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
    async def send_message(cls, event: MessageEvent) -> list[MessageSegment]:
        # sourcery skip: use-fstring-for-formatting
        match ChatConfig.get("CHAT_MODE"):
            case "user":
                uid = str(event.sender.user_id)
            case "group":
                uid = "g-" + (
                    str(event.group_id)  # type: ignore
                    if hasattr(event, "group_id")
                    else str(event.sender.user_id)
                )
            case "all":
                uid = "mix_mode"
            case _:
                raise ValueError("CHAT_MODE must be 'user', 'group' or 'all'")
        user_name = await cls.get_user_nickname(event)
        await cls.add_system_message(ChatConfig.get("SOUL"), uid)
        message = await cls.get_message(event)
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
        result = await cls.get_zhipu_result(
            uid, ChatConfig.get("CHAT_MODEL"), cls.chat_history[uid]
        )
        if isinstance(result, list):
            logger.info(f"USER {uid} 问题: {words} ---- 触发内容审查", "zhipu_toolkit")
            return result
        await cls.add_message(result, uid, role="assistant")
        logger.info(f"USER {uid} 问题：{words} ---- 回答：{result}", "zhipu_toolkit")
        return [MessageSegment.text(result)]

    @classmethod
    async def add_message(cls, words: str, uid: str, role="user") -> None:
        cls.chat_history[uid].append({"role": role, "content": words})
        await cls.check_token(uid, len(words))

    @classmethod
    async def add_system_message(cls, soul: str, uid: str) -> None:
        if cls.chat_history.get(uid) is None:
            cls.chat_history[uid] = [{"role": "system", "content": soul}]

    @classmethod
    async def clear_history(cls, uid: str | None = None) -> int:
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
    async def get_message(cls, event: MessageEvent) -> str:
        message = ""
        for segment in event.get_message():
            if segment.type == "image":
                message += "\n[图片,描述:{}]".format(
                    await cls.__generate_image_description(
                        segment.data["url"].replace("https://", "http://")
                    )
                )
            elif segment.type == "text":
                message += segment.data["text"]
            elif segment.type == "at":
                message += f"@{segment.data['qq']}"
            elif segment.type == "share":
                message += f"[分享内容,标题:{segment.data['title']}]"
        return message

    @classmethod
    async def get_user_nickname(cls, event: MessageEvent) -> str:
        if hasattr(event.sender, "card") and event.sender.card:
            return event.sender.card
        return event.sender.nickname if event.sender.nickname is not None else "None"

    @classmethod
    async def impersonation_result(
        cls, event: GroupMessageEvent
    ) -> MessageSegment | None:
        gid = str(event.group_id)
        nickname = await cls.get_user_nickname(event)
        uid = str(event.sender.user_id)
        if not (group_msg := GROUP_MSG_CACHE[gid]):
            return

        content = "".join(
            f"{msg.nickname} ({msg.uid})说:\n{msg.msg}\n\n" for msg in group_msg
        )
        head = f"你在一个QQ群里，群号是{gid},当前和你说话的人昵称是'{nickname}'', QQ号是{uid}, 请你结合该群的聊天记录作出回应，要求表现得随性一点，需要参与讨论，混入其中。不要过分插科打诨，不要提起无关的话题，不知道说什么可以复读群友的话。不允许包含聊天记录的格式。如果觉得此时不需要自己说话，只回复<EMPTY>下面是群组的聊天记录：\n\n"  # noqa: E501
        foot = "\n\n你的回复应该尽可能简练,一次只说一句话，像人类一样随意，不要附加任何奇怪的东西，如聊天记录的格式，禁止重复聊天记录。不允许有无意义的语气词和emoji。"  # noqa: E501
        result = await cls.get_zhipu_result(
            str(uuid.uuid4()),
            ChatConfig.get("IMPERSONATION_MODEL"),
            [
               {
                  "role": "system",
                  "content": f"你需要遵循以下要求，同时保证回应中不包含聊天记录格式。{ChatConfig.get('SOUL')}"
               },
                {
                    "role": "user",
                    "content": head + content + foot,
                }
            ],
        )
        if isinstance(result, list):
            logger.info(f"GROUP {gid} USER {uid} ---- 伪人触发内容审查", "zhipu_toolkit")
            return
        if "<EMPTY>" in result:
            logger.info(f"GROUP {gid} USER {uid} ---- 伪人不需要回复，已被跳过", "zhipu_toolkit")
            return
        logger.info(f"GROUP {gid} USER {uid}  ---- 伪人回复: {result}", "zhipu_toolkit")
        return MessageSegment.text(result)

    @classmethod
    async def get_zhipu_result(
        cls, uid: str, model: str, messages: list
    ) -> str | list[MessageSegment]:
        loop = asyncio.get_event_loop()
        client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=model,
                    messages=messages,
                    user_id=uid,
                ),
            )
        except Exception as e:
            return [
                MessageSegment.text(f"{e!s}\n\n如需清理对话记录，请发送'清理我的会话'")
            ]
        return response.choices[0].message.content  # type: ignore

    @classmethod
    async def __generate_image_description(cls, url: str):
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
        return result
