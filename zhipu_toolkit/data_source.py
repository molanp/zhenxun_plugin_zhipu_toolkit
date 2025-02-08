import asyncio
import datetime
import random
import os
from zhipuai import ZhipuAI
from zhenxun.configs.path_config import IMAGE_PATH
from zhenxun.configs.config import BotConfig
from nonebot_plugin_alconna import Text, Video
from nonebot.adapters.onebot.v11 import Event
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
    chat_history = {}
    chat_history_token = {}

    @classmethod
    async def check_token(cls, uid: str, token_len: int):
        return  # 暂时没用，文档似乎说是单条token最大4095
        if cls.chat_history_token.get(uid) is None:
            cls.chat_history_token[uid] = 0
        cls.chat_history_token[uid] += token_len

        user_history = cls.chat_history.get(uid, [])
        while cls.chat_history_token[uid] > 4095 and len(user_history) > 1:
            removed_token_len = len(user_history[1]["content"])
            user_history = user_history[1:]
            cls.chat_history_token[uid] -= removed_token_len

        cls.chat_history[uid] = user_history

    @classmethod
    async def send_message(cls, event: Event) -> str:
        uid = str(event.sender.user_id)
        user_name = (event.sender.card if hasattr(event.sender, 'card') and event.sender.card else event.sender.nickname)
        words = f"现在是{datetime.datetime.fromtimestamp(event.time).strftime('%Y-%m-%d %H:%M:%S')}, 我叫'{user_name}'。我想说: {event.get_plaintext()}"
        if len(words) > 4095:
            return "超出最大token限制: 4095"
        await cls.add_message(words, uid)
        loop = asyncio.get_event_loop()
        client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=ChatConfig.get("CHAT_MODEL"),
                    messages=cls.chat_history[uid],
                    user_id=uid
                ),
            )
        except Exception as e:
            return f"Error: {e!s}" + "\n\n如需清理对话记录，请发送'清理我的会话'"
        result = response.choices[0].message.content  # type: ignore
        await cls.add_message(result, uid, role="assistant")  # type: ignore
        return result  # type: ignore

    @classmethod
    async def add_message(cls, words: str, uid: str, role="user"):
        if cls.chat_history.get(uid) is None:
            cls.chat_history[uid] = [{
               "role": "system", 
               "content": 
                  ChatConfig.get("SOUL")
           }]
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
