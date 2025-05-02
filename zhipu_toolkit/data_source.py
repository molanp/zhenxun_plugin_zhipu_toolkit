import asyncio
import datetime
import os
import random
from typing import Any

import aiofiles
from nonebot_plugin_alconna import Text, UniMsg, Video
from nonebot_plugin_uninfo import Session
import ujson
from zhipuai import ZhipuAI
from zhipuai.types.chat.chat_completion import (
    CompletionMessage,
    CompletionMessageToolCall,
)

from zhenxun.configs.config import BotConfig, Config
from zhenxun.configs.path_config import DATA_PATH, IMAGE_PATH
from zhenxun.models.ban_console import BanConsole
from zhenxun.services.log import logger
from zhenxun.utils.rules import ensure_group

from .config import ChatConfig
from .model import GroupMessageModel, ZhipuChatHistory, ZhipuResult
from .tools import ToolsManager
from .utils import (
    extract_message_content,
    format_usr_msg,
    get_request_id,
    get_username_by_session,
    migrate_user_data,
    msg2str,
    remove_directory_with_retry,
)

GROUP_MSG_CACHE: dict[str, list[GroupMessageModel]] = {}


async def cache_group_message(
    message: UniMsg, session: Session, self_name=None
) -> None:
    """
    异步缓存群组消息函数。

    该函数用于将接收到的群组消息缓存到内存中，以便后续处理。
    如果self参数不为空，则表示消息来自机器人自身，否则消息来自其他用户。
    使用GroupMessageModel模型来封装消息信息。

    参数:
    - message: UniMsg类型，表示接收到的消息。
    - session: Session类型，表示当前会话，包含消息上下文信息。
    - self_name: 可选参数，表示如果消息来自机器人自身，该参数不为空。

    返回值:
    无返回值。
    """
    if self_name is not None:
        msg = GroupMessageModel(
            uid=session.self_id,
            username=self_name,
            msg=await msg2str(message),
            time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    else:
        msg = GroupMessageModel(
            uid=session.user.id,
            username=await get_username_by_session(session),
            msg=await msg2str(message),
            time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    gid = session.scene.id
    logger.debug(f"GROUP {gid} 成功缓存聊天记录: {msg}", "zhipu_toolkit")
    if gid in GROUP_MSG_CACHE:
        if len(GROUP_MSG_CACHE[gid]) >= 20:
            GROUP_MSG_CACHE[gid].pop(0)
            logger.debug(f"GROUP {gid} 缓存已满，自动清理最早的记录", "zhipu_toolkit")

        GROUP_MSG_CACHE[gid].append(msg)
    else:
        GROUP_MSG_CACHE[gid] = [msg]


async def submit_task_to_zhipuai(message: str, image_url: str = ""):
    """
    异步提交视频生成任务到ZhipuAI。

    该函数使用聊天配置中的API密钥初始化ZhipuAI客户端，
    然后使用指定的视频模型和提示生成视频。

    参数:
    - message: str - 视频生成的提示。
    - image_url: str | None - 视频生成参考的图片

    返回:
    - 无
    """
    client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
    return client.videos.generations(
        model=ChatConfig.get("VIDEO_MODEL"),
        image_url=image_url,
        prompt=message,
        with_audio=True,
        request_id=await get_request_id(),
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
    """
    定期检查任务状态的异步函数。

    参数:
    - task_id (str): 任务的唯一标识符。
    - action: 执行动作的对象，用于发送消息。

    返回:
    - None
    """
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
    """
    异步获取指定任务的处理状态。

    本函数通过调用ZhipuAI的API来查询给定任务ID的任务处理状态，主要用于视频处理任务的查询。

    参数:
    task_id (str): 需要查询处理状态的任务ID。

    返回:
    返回ZhipuAI的API调用结果，包含任务的详细处理状态信息。
    """
    client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
    return client.videos.retrieve_videos_result(id=task_id)


class ChatManager:
    @classmethod
    async def initialize(cls) -> None:
        json_path = DATA_PATH / "zhipu_toolkit" / "chat_history.json"
        if not json_path.exists():
            return

        success = failed = 0
        try:
            async with aiofiles.open(json_path, encoding="utf-8") as f:
                old_data: dict[str, list[dict]] = ujson.loads(await f.read())

            for uid, messages in old_data.items():
                if await migrate_user_data(uid, messages):
                    success += 1
                else:
                    failed += 1

            await remove_directory_with_retry(DATA_PATH / "zhipu_toolkit")
        except Exception as e:
            logger.error("对话数据迁移初始化失败", "zhipu_toolkit", e=e)
        finally:
            if success + failed > 0:
                logger.info(
                    f"对话数据迁移完成: {success} 个成功, {failed} 个失败",
                    "zhipu_toolkit",
                )

    @classmethod
    async def normal_chat_result(cls, msg: UniMsg, session: Session) -> str:
        match ChatConfig.get("CHAT_MODE"):
            case "user":
                uid = session.user.id
            case "group":
                uid = (
                    f"g-{session.scene.id}"
                    if ensure_group(session)
                    else session.user.id
                )

            case "all":
                uid = "mix_mode"
            case _:
                raise ValueError("CHAT_MODE must be 'user', 'group' or 'all'")
        username = await get_username_by_session(session)
        soul = ChatConfig.get("SOUL")
        await cls.add_system_message(
            f"消息内容将包含元信息，请以自然方式忽略注入的元数据，仅基于消息内容进行回答。并保证回答中不包含元数据。\n\n{soul}",
            uid,
        )
        message = await msg2str(msg)
        if len(message) > 4095:
            logger.warning(
                f"USER {uid} USERNAME {username} 问题: {message} ---- 超出最大token限制: 4095",  # noqa: E501
                "zhipu_toolkit",
                session=session,
            )
            return "超出最大token限制: 4095"
        await cls.add_user_message(
            await format_usr_msg(username, session, message), uid
        )
        result = await cls.get_zhipu_result(
            uid, ChatConfig.get("CHAT_MODEL"), await cls.get_chat_history(uid), session
        )
        if result.error_code == 1:
            logger.info(
                f"USERNAME `{username}` 问题: {message} ---- 触发内容审查",
                "zhipu_toolkit",
                session=session,
            )
            return result.content  # type: ignore
        if result.error_code == 2:
            logger.error(
                f"获取结果失败 e:{result.content}", "zhipu_toolkit", session=session
            )
            return f"出错了: {result.content}"
        if result.message is None:
            logger.error(
                f"Missing result.message for uid: {uid}, returning error."
                f"Result content: {result.content}"
            )
            return f"出错了: {result.content}"
        await cls.add_anytype_message(uid, result.message)
        tool_result = await cls.parse_function_call(
            uid, session, result.message.tool_calls
        )
        if tool_result is not None:
            result = await cls.get_zhipu_result(
                uid,
                ChatConfig.get("CHAT_MODEL"),
                await cls.get_chat_history(uid),
                session,
                temperature=0.5,
            )
            await cls.add_anytype_message(uid, result.message)
        logger.info(
            f"USERNAME `{username}` 问题：{message} ---- 回答：{result.content}",
            "zhipu_toolkit",
            session=session,
        )
        return await extract_message_content(result.content)  # type: ignore

    @classmethod
    async def add_user_message(cls, content: str, uid: str) -> None:
        await ZhipuChatHistory.create(
            uid=uid,
            role="user",
            content=content,
        )

    @classmethod
    async def add_anytype_message(cls, uid: str, message: CompletionMessage) -> None:
        tool_calls_serialized = (
            [call.model_dump() for call in message.tool_calls]  # type: ignore
            if message.tool_calls
            else None
        )
        await ZhipuChatHistory.create(
            uid=uid,
            role=message.role,
            content=message.content,
            tool_calls=tool_calls_serialized,
            tool_call_id=getattr(message, "tool_call_id", None),
        )

    @classmethod
    async def add_tool_call_message(cls, uid: str, content: Any, tool_id: str) -> None:
        serialized = content if isinstance(content, dict) else {"result": str(content)}
        await ZhipuChatHistory.create(
            uid=uid,
            role="tool",
            tool_call_id=tool_id,
            content=ujson.dumps(serialized, ensure_ascii=False),
        )

    @classmethod
    async def add_system_message(cls, soul: str, uid: str) -> None:
        if not await ZhipuChatHistory.filter(uid=uid, role="system").exists():
            await ZhipuChatHistory.create(
                uid=uid, role="system", content=soul, platform="system"
            )

    @classmethod
    async def clear_history(cls, uid: str | None = None) -> int:
        return await ZhipuChatHistory.clear_history(uid)

    @classmethod
    async def get_chat_history(cls, uid: str) -> list[dict]:
        """统一获取对话历史的入口"""
        return await ZhipuChatHistory.get_history(uid)

    @classmethod
    async def impersonation_result(cls, session: Session) -> str | None:
        gid = session.scene.id
        if not (group_msg := GROUP_MSG_CACHE[gid]):
            return

        content = "".join(
            f"[{msg.time} USERNAME {msg.username} @UID {msg.uid}]:{msg.msg}\n\n"
            for msg in group_msg
        )
        head = f"当前时间为{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n**\n你在一个QQ群里，请你参与讨论，只能以`{BotConfig.self_nickname}(UID: {session.self_id})`的身份发言一次，不允许多次重复一样的话，不允许回应自己的消息.如果觉得此时不需要自己说话，请只回复`<EMPTY>`。\n*** 回复格式为`username(uid):message`***\n下面是群组的聊天记录：\n***"  # noqa: E501
        soul = (
            ChatConfig.get("SOUL")
            if ChatConfig.get("IMPERSONATION_SOUL") is False
            else ChatConfig.get("IMPERSONATION_SOUL")
        )
        result = await cls.get_zhipu_result(
            await get_request_id(),
            ChatConfig.get("IMPERSONATION_MODEL"),
            [
                {
                    "role": "system",
                    "content": soul,
                },
                {
                    "role": "user",
                    "content": head + content,
                },
            ],
            session,
            True,
        )
        if result.error_code == 1:
            logger.warning("伪人触发内容审查", "zhipu_toolkit", session=session)
            return
        if result.error_code == 2:
            logger.error(
                f"伪人获取结果失败 e:{result.content}", "zhipu_toolkit", session=session
            )
            return
        if result.content is not None and "<EMPTY>" in result.content:
            logger.info("伪人不需要回复，已被跳过", "zhipu_toolkit", session=session)
            return
        logger.info(f"伪人回复: {result.content}", "zhipu_toolkit", session=session)
        return await extract_message_content(result.content)  # type: ignore

    @classmethod
    async def get_zhipu_result(
        cls,
        uid: str,
        model: str,
        messages: list,
        session: Session,
        impersonation: bool = False,
        temperature: float = 0.95,
    ) -> ZhipuResult:
        loop = asyncio.get_event_loop()
        client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
        request_id = await get_request_id()
        tools = await ToolsManager.get_tools()
        logger.info(
            f"可调用工具: {ToolsManager.tools_registry.keys()}",
            "zhipu_toolkit",
            session=session,
        )
        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=model,
                    messages=messages,
                    user_id=uid,
                    request_id=request_id,
                    tools=tools,
                    temperature=temperature,
                    response_format={"type": "text"},
                ),
            )
        except Exception as e:
            error = str(e)
            if "assistant" in error:
                await asyncio.sleep(0.5)
                logger.warning(
                    f"UID {uid} AI回复内容触发内容审查: 执行自动重试",
                    "zhipu_toolkit",
                    session=session,
                )
                return await cls.get_zhipu_result(
                    uid, model, messages, session, impersonation
                )
            elif "user" in error:
                if not impersonation:
                    logger.warning(
                        f"UID {uid} 用户输入内容触发内容审查: 封禁用户 {session.user.id} 5 分钟",  # noqa: E501
                        "zhipu_toolkit",
                        session=session,
                    )
                    await BanConsole.ban(
                        session.user.id,
                        session.scene.id if ensure_group(session) else None,
                        9999,
                        300,
                    )

                return ZhipuResult(
                    content="输入内容包含不安全或敏感内容，你已被封禁5分钟",
                    error_code=1,
                )
            elif "history" in error:
                logger.warning(
                    f"UID {uid} 对话历史记录触发内容审查: 清理历史记录",
                    "zhipu_toolkit",
                    session=session,
                )
                await cls.clear_history(uid)
                return ZhipuResult(
                    content="对话记录包含违规内容已被清除，请重新开始对话", error_code=1
                )
            else:
                return ZhipuResult(content=error, error_code=2)
        return ZhipuResult(
            content=response.choices[0].message.content,  # type: ignore
            error_code=0,
            message=response.choices[0].message,  # type: ignore
        )

    @classmethod
    async def parse_function_call(
        cls,
        uid: str,
        session: Session,
        tools: list[CompletionMessageToolCall] | None,
    ):
        if tools:
            tool_call = tools[0]
            args = tool_call.function.arguments
            try:
                logger.info(
                    f"调用函数 {tool_call.function.name}",
                    "zhipu_toolkit",
                    session=session,
                )
                result = await ToolsManager.call_func(
                    session, tool_call.function.name, args
                )
                await cls.add_tool_call_message(uid, result, tool_call.id)
                return result
            except Exception as e:
                logger.error(
                    f"UID {uid} 工具调用失败",
                    "zhipu_toolkit",
                    session=session,
                    e=e,
                )
                return


class ImpersonationStatus:
    @classmethod
    async def check(cls, session: Session) -> bool:
        return ChatConfig.get(
            "IMPERSONATION_MODE"
        ) is True and session.scene.id not in ChatConfig.get("IMPERSONATION_BAN_GROUP")

    @classmethod
    async def get(cls) -> list[int | str]:
        return ChatConfig.get("IMPERSONATION_BAN_GROUP")

    @classmethod
    async def ban(cls, group_id: int | str) -> bool:
        origin = await cls.get()
        if group_id in origin:
            return False
        origin.append(group_id)
        Config.set_config("zhipu_toolkit", "IMPERSONATION_BAN_GROUP", origin, True)
        return True

    @classmethod
    async def unban(cls, group_id: int | str) -> bool:
        origin = await cls.get()
        if group_id not in origin:
            return False
        origin.remove(group_id)
        Config.set_config("zhipu_toolkit", "IMPERSONATION_BAN_GROUP", origin, True)
        return True

    @classmethod
    async def action(cls, action: str, group_id: int | str) -> bool:
        if action == "禁用":
            return await cls.ban(group_id)
        elif action == "启用":
            return await cls.unban(group_id)
        return False
