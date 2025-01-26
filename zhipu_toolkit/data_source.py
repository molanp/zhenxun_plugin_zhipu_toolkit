import asyncio
import random
import os
from zhenxun.configs.path_config import IMAGE_PATH
from zhenxun.configs.config import BotConfig
from nonebot_plugin_alconna import Text, Video

from .config import client, soul


async def submit_task_to_zhipuai(message: str):
    return client.videos.generations(
        model="cogvideox-flash",
        prompt=message,
        with_audio=True,
    )

async def hello() -> list:
    """一些打招呼的内容"""
    result = random.choice(
        (
            "哦豁？！",
            "你好！Ov<",
            f"库库库，呼唤{BotConfig.self_nickname}做什么呢",
            "我在呢！",
            "呼呼，叫俺干嘛",
        )
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
                await action.send(Text("生成失败了.."), reply_to=True)
            await asyncio.sleep(5)


async def check_task_status_from_zhipuai(task_id: str):
    return client.videos.retrieve_videos_result(id=task_id)


class ChatManager:
    chat_history = {}  # noqa: RUF012
    chat_history_token = {}  # noqa: RUF012
    system_soul = {"role": "system", "content": soul}  # noqa: RUF012

    @classmethod
    async def check_token(cls, uid: str, token_len: int):
        return #暂时没用，文档似乎说是单条token4095
        if cls.chat_history_token.get(uid) is None:
            cls.chat_history_token[uid] = 0
        cls.chat_history_token[uid] += token_len
        # 检查是否超限
        user_history = cls.chat_history.get(uid, [])
        while cls.chat_history_token[uid] > 4095 and len(user_history) > 1:
            # 计算要删除的历史项的token长度
            removed_token_len = len(user_history[1]["content"])
            user_history = user_history[1:]
            # 更新token计数
            cls.chat_history_token[uid] -= removed_token_len

        cls.chat_history[uid] = user_history

    @classmethod
    async def send_message(cls, words: str, user_id: int, role="user") -> str:
        uid = str(user_id)
        if len(words) > 4095: 
           return "超出最大token限制: 4095"
        await cls.add_message(words, user_id)
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model="glm-4-flash",
                    messages=cls.chat_history[uid],
                    user_id=uid
                ),
            )
        except Exception as e:
            return f"Error: {e!s}"
        result = response.choices[0].message.content  # type: ignore
        await cls.add_message(result, user_id, role="assistant")  # type: ignore
        return result # type: ignore

    @classmethod
    async def add_message(cls, words: str, user_id: int, role="user"):
        uid = str(user_id)
        if cls.chat_history.get(uid) is None:
            cls.chat_history[uid] = [cls.system_soul]
        cls.chat_history[uid].append({"role": role, "content": words})
        await cls.check_token(uid, len(words))

    @classmethod
    async def clear_history(cls, user_id: int):
        uid = str(user_id)
        if cls.chat_history.get(uid) is None:
            return 0
        count = len(cls.chat_history[uid])
        del cls.chat_history[uid]
        return count
