import asyncio
import datetime
import os
import random
from typing import Any

from nonebot import require
import ujson

from zhenxun.models.chat_history import ChatHistory

require("nonebot_plugin_alconna")
require("nonebot_plugin_uninfo")
from nonebot_plugin_alconna import AlconnaMatcher, Text, UniMessage, Video
from nonebot_plugin_uninfo import Session
from zai import ZhipuAiClient as ZhipuAI
from zai.types.chat.chat_completion import CompletionMessage, CompletionMessageToolCall

from zhenxun.configs.config import BotConfig, Config
from zhenxun.configs.path_config import IMAGE_PATH
from zhenxun.models.ban_console import BanConsole
from zhenxun.services.log import logger
from zhenxun.utils.rules import ensure_group

from .config import IMPERSONATION_PROMPT, ChatConfig, get_prompt
from .model import ZhipuChatHistory, ZhipuResult
from .tools import ToolsManager
from .utils import (
    extract_message_content,
    format_usr_msg,
    get_request_id,
    get_username,
    get_username_by_session,
    msg2str,
)


def hello() -> list:
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


async def check_video_task_status(task_id: str, action: type[AlconnaMatcher]):
    """定期检查视频生成任务状态，并在任务完成后自动结束"""
    while True:
        try:
            client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
            response = await asyncio.to_thread(
                client.videos.retrieve_videos_result, id=task_id
            )

            if response.task_status == "SUCCESS":
                await action.send(Video(url=response.video_result[0].url))
                return

            elif response.task_status == "FAIL":
                await action.send(Text("生成失败了。"), reply_to=True)
                return

            await asyncio.sleep(2)

        except Exception as e:
            raise e


class ChatManager:
    @classmethod
    async def normal_chat_result(cls, msg: UniMessage, session: Session) -> str:
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
        username = get_username_by_session(session)
        await cls.add_system_message(uid)
        message, img_url = await msg2str(msg, bool(ChatConfig.get("IS_MULTIMODAL")))
        word_limit = ChatConfig.get("WORD_LIMIT")
        if len(message) > word_limit:
            logger.warning(
                f"USER {uid} USERNAME {username} 问题: {message} ---- 超出字数限制: {word_limit}",  # noqa: E501
                "zhipu_toolkit",
                session=session,
            )
            return f"超出管理员设置的字数限制: {word_limit}"
        await cls.add_user_message(
            format_usr_msg(username, session, message), uid, img_url
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
            await ZhipuChatHistory.delete_latest_record(uid)
            return result.content  # pyright: ignore[reportReturnType]
        if result.error_code == 2:
            logger.error(
                f"获取结果失败 e:{result.content}", "zhipu_toolkit", session=session
            )
            await ZhipuChatHistory.delete_latest_record(uid)
            return f"出错了: {result.content}"
        if result.message is None:
            logger.error(
                f"Missing result.message for uid: {uid}, returning error."
                f"Result content: {result.content}"
            )
            await ZhipuChatHistory.delete_latest_record(uid)
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
                use_tool=False,
            )
            await cls.add_anytype_message(uid, result.message)  # type: ignore
        answer = extract_message_content(result.content)
        assert isinstance(answer, str)
        logger.info(
            f"USERNAME `{username}` 问题：{message} ---- 回答：{answer}",
            "zhipu_toolkit",
            session=session,
        )
        return answer

    @classmethod
    async def add_user_message(
        cls, content: str, uid: str, res_url: str | None = None
    ) -> None:
        await ZhipuChatHistory.create(
            uid=uid,
            role="user",
            content=content,
            res_url=res_url,
        )

    @classmethod
    async def add_anytype_message(cls, uid: str, message: CompletionMessage) -> None:
        tool_calls_serialized = (
            [call.model_dump() for call in message.tool_calls]
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
    async def add_system_message(cls, uid: str) -> None:
        if not await ZhipuChatHistory.filter(uid=uid, role="system").exists():
            soul = await get_prompt()
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
    async def call_impersonation_ai(cls, session: Session):
        gid = session.scene.id

        rows = (
            await ChatHistory.filter(group_id=gid)
            .order_by("-create_time")
            .limit(20)
            .values("bot_id", "user_id", "group_id", "create_time", "text")
        )
        if not rows:
            logger.warning(
                f"数据库中未找到群 {gid} 的聊天记录",
                command="zhipu_toolkit",
                session=session,
            )
            return

        # 本地缓存相同 (bot_id,user_id,group_id) 的用户名，避免重复查询
        def _key_from_row(r):
            return (r["bot_id"], r["user_id"], r["group_id"])
        unique_keys = {}
        tasks = []
        for r in rows:
            key = _key_from_row(r)
            if key not in unique_keys:
                unique_keys[key] = None
                tasks.append(get_username(*key))

        # 并发获取所有不同用户的用户名
        if tasks:
            results = await asyncio.gather(*tasks)
            # 填回缓存（注意 tasks 与 unique_keys 顺序一致）
            for key, name in zip(list(unique_keys.keys()), results):
                unique_keys[key] = name

        # 构建聊天记录字符串（列表收集，最后 join）
        parts = []
        for r in rows:
            uname = unique_keys[_key_from_row(r)]
            parts.append(f"{r['create_time']} [{uname}]: {r['text']}")
        CHAT_RECORDS = "\n\n".join(parts)

        prompt = IMPERSONATION_PROMPT.format(
            date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            name=BotConfig.self_nickname,
            uid=session.self_id,
            soul=await get_prompt(),
        )
        result = await cls.get_zhipu_result(
            get_request_id(),
            ChatConfig.get("IMPERSONATION_MODEL"),
            [
                {
                    "role": "system",
                    "content": prompt,
                },
                {"role": "user", "content": CHAT_RECORDS},
            ],
            session,
            True,
            use_tool=False,
        )
        if result.error_code == 1:
            logger.warning("伪人触发内容审查", "zhipu_toolkit", session=session)
            return
        answer = result.content
        if result.error_code == 2:
            logger.error(
                f"伪人获取结果失败 e:{answer}", "zhipu_toolkit", session=session
            )
            return
        if answer is not None and "<EMPTY>" in answer:
            logger.info("伪人不需要回复，已被跳过", "zhipu_toolkit", session=session)
            return
        logger.info(f"伪人回复: {answer}", "zhipu_toolkit", session=session)
        answer = extract_message_content(answer)
        await UniMessage(answer).send()

    @classmethod
    async def get_zhipu_result(
        cls,
        uid: str,
        model: str,
        messages: list[dict[str, str]],
        session: Session,
        impersonation: bool = False,
        use_tool: bool = True,
    ) -> ZhipuResult:
        loop = asyncio.get_event_loop()
        client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
        request_id = get_request_id()
        tools = (await ToolsManager.get_tools()) if use_tool else None
        tool_map = ToolsManager.tools_registry.keys() if tools else None
        logger.info(
            f"可调用工具: {tool_map}",
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
                ),
            )
        except Exception as e:
            error = str(e)
            if "user" in error:
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
                        "输入内容违规",
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
    async def get(cls) -> list[str]:
        return ChatConfig.get("IMPERSONATION_BAN_GROUP")

    @classmethod
    async def ban(cls, group_id: str) -> bool:
        origin = await cls.get()
        if group_id in origin:
            return False
        origin.append(group_id)
        Config.set_config("zhipu_toolkit", "IMPERSONATION_BAN_GROUP", origin, True)
        return True

    @classmethod
    async def unban(cls, group_id: str) -> bool:
        origin = await cls.get()
        if group_id not in origin:
            return False
        origin.remove(group_id)
        Config.set_config("zhipu_toolkit", "IMPERSONATION_BAN_GROUP", origin, True)
        return True

    @classmethod
    async def action(cls, action: str, group_id: str) -> bool:
        if action == "禁用":
            return await cls.ban(group_id)
        elif action == "启用":
            return await cls.unban(group_id)
        return False
