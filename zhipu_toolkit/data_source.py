import asyncio
from dataclasses import dataclass, field
import datetime
import os
from pathlib import Path
import random
from typing import Any

from nonebot_plugin_alconna import AlconnaMatcher, Text, UniMessage, Video
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_uninfo import Uninfo
from zai import ZhipuAiClient as ZhipuAI
from zai.types.chat.chat_completion import CompletionMessage, CompletionMessageToolCall

from zhenxun.configs.config import BotConfig, Config
from zhenxun.configs.path_config import IMAGE_PATH
from zhenxun.models.ban_console import BanConsole
from zhenxun.models.chat_history import ChatHistory
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
    is_harmful_output,
)

# ==== 简单的内存缓存，用于减少 normal_chat 频繁扫数据库 ====

# 缓存有效期：多久没有访问就认为过期，自动丢弃
CHAT_HISTORY_TTL_SECONDS = 120 * 60  # 120 分钟
# 每个 uid 最多保留多少条历史记录，防止内存无限增长
CHAT_HISTORY_MAX_LEN = 200


@dataclass
class HistoryEntry:
    last_access: datetime.datetime
    data: list[dict[str, Any]]


@dataclass
class HistoryCache:
    ttl_seconds: int
    max_len: int
    _store: dict[str, HistoryEntry] = field(default_factory=dict)

    def get(self, uid: str) -> list[dict] | None:
        now = datetime.datetime.now()
        info = self._store.get(uid)
        if not info:
            return None
        if (now - info.last_access).total_seconds() > self.ttl_seconds:
            self._store.pop(uid, None)
            return None
        info.last_access = now
        return info.data

    def set(self, uid: str, history: list[dict[str, Any]]) -> None:
        self._store[uid] = HistoryEntry(
            last_access=datetime.datetime.now(),
            data=history[-self.max_len :],
        )

    def add_records(self, uid: str, records: list[dict[str, Any]]) -> None:
        if uid not in self._store:
            return
        history = self._store[uid].data
        history.extend(records)
        self._store[uid].data = history[-self.max_len :]
        self._store[uid].last_access = datetime.datetime.now()

    def clear(self, uid: str | None = None) -> None:
        if uid is None:
            self._store.clear()
        else:
            self._store.pop(uid, None)

    def prune(self) -> int:
        now = datetime.datetime.now()
        expired = [
            uid
            for uid, info in self._store.items()
            if (now - info.last_access).total_seconds() > self.ttl_seconds
        ]
        for uid in expired:
            self._store.pop(uid, None)
        if expired:
            logger.debug(
                f"normal_chat 缓存清理: 移除 {len(expired)} 个 uid 的历史缓存",
                "zhipu_toolkit",
            )
        return len(expired)


_history_cache = HistoryCache(CHAT_HISTORY_TTL_SECONDS, CHAT_HISTORY_MAX_LEN)


@scheduler.scheduled_job("interval", minutes=100, id="zhipu_normal_chat_cache_prune")
async def prune_history_cache_job() -> None:
    """定时任务：周期性清理 normal_chat 的内存缓存."""
    _history_cache.prune()


def hello() -> tuple[str, Path]:
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
    return result, IMAGE_PATH / "zai" / img


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
                break

            elif response.task_status == "FAIL":
                await action.send(Text("生成失败了..."), reply_to=True)
                break
            await asyncio.sleep(2)

        except Exception as e:
            await action.send(Text(str(e)), reply_to=True)
            break


class ChatManager:
    @classmethod
    def _build_user_record(cls, content: str, res_url: str | None = None) -> dict:
        """构造一条 user 记录（仅内存使用，不直接写 DB）"""
        return {
            "role": "user",
            "content": content,
            "res_url": res_url,
            "tool_calls": None,
            "tool_call_id": None,
        }

    @classmethod
    def _build_assistant_record(
        cls,
        message: CompletionMessage,
    ) -> dict:
        """构造一条 assistant 记录（仅内存使用，不直接写 DB）"""
        tool_calls_serialized = (
            [call.model_dump() for call in message.tool_calls]
            if message.tool_calls
            else None
        )
        return {
            "role": message.role,
            "content": message.content,
            "res_url": None,
            "tool_calls": tool_calls_serialized,
            "tool_call_id": getattr(message, "tool_call_id", None),
        }

    @classmethod
    def _build_tool_record(cls, content: str, tool_id: str) -> dict:
        """构造一条 tool 调用记录（仅内存使用，不直接写 DB）"""
        return {
            "role": "tool",
            "content": content,
            "res_url": None,
            "tool_calls": None,
            "tool_call_id": tool_id,
        }

    @classmethod
    @classmethod
    async def _resolve_tool_chain(
        cls,
        uid: str,
        session: Uninfo,
        round_records: list[dict],
        max_tool_calls: int,
        initial_result: ZhipuResult,
    ) -> ZhipuResult:
        """处理模型可能发起的一条或多条工具调用链。"""
        if max_tool_calls <= 0 or initial_result.message is None:
            return initial_result

        result = initial_result
        used_tool_calls = 0

        while (
            result.message
            and result.message.tool_calls
            and used_tool_calls < max_tool_calls
        ):
            tool_calls = result.message.tool_calls
            for tool_call in tool_calls:
                # 如果已经达到上限，在当前 tool_call 上补一条“已达上限”的 tool 结果并终止链路
                if used_tool_calls >= max_tool_calls:
                    logger.warning(
                        f"达到单次对话最大工具调用次数 {max_tool_calls}，后续工具调用将被忽略",
                        "zhipu_toolkit",
                        session=session,
                    )
                    round_records.append(
                        cls._build_tool_record(
                            "本次对话工具调用次数已达上限", tool_call.id
                        )
                    )
                    return result

                tool_result = await cls.parse_function_call(session, tool_call)
                round_records.append(cls._build_tool_record(tool_result, tool_call.id))
                used_tool_calls += 1

            # 当前这轮 tool_calls 处理完后，如果已经达到上限，则不再让模型继续发起新的工具调用
            if used_tool_calls >= max_tool_calls:
                break

            result = await cls.get_zhipu_result(
                uid,
                ChatConfig.get("CHAT_MODEL"),
                await cls.get_chat_history(uid) + round_records,
                session,
                use_tool=used_tool_calls < max_tool_calls,
            )
            if result.error_code != 0 or result.message is None:
                return result

            round_records.append(cls._build_assistant_record(result.message))

        return result

    @classmethod
    async def _flush_round_history(cls, uid: str, records: list[dict]) -> None:
        """将一轮对话（用户 + 模型返回 + 工具调用）写入数据库并同步更新缓存。

        前提:
            - 调用方保证只有在模型返回结构正常时才调用。
        """
        if not records:
            return

        # 1. 顺序写入数据库
        for rec in records:
            await ZhipuChatHistory.create(
                uid=uid,
                role=rec["role"],
                content=rec["content"],
                res_url=rec.get("res_url"),
                tool_calls=rec.get("tool_calls"),
                tool_call_id=rec.get("tool_call_id"),
            )

        # 2. 同步更新内存缓存
        _history_cache.add_records(
            uid,
            [
                {
                    "role": rec["role"],
                    "content": (
                        [
                            {"type": "text", "text": rec["content"]},
                            {
                                "type": "image_url",
                                "image_url": {"url": rec["res_url"]},
                            },
                        ]
                        if rec.get("res_url")
                        else rec["content"]
                    ),
                    "tool_call_id": rec.get("tool_call_id"),
                    "tool_calls": rec.get("tool_calls"),
                }
                for rec in records
            ],
        )

    @classmethod
    async def normal_chat_result(cls, msg: UniMessage, session: Uninfo) -> str:
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
        message, img_url = await msg2str(msg, bool(ChatConfig.get("IS_MULTIMODAL")))
        word_limit = ChatConfig.get("WORD_LIMIT")
        if len(message) > word_limit:
            logger.warning(
                f"USER {uid} USERNAME {username} 问题: {message} ---- 超出字数限制: {word_limit}",  # noqa: E501
                "zhipu_toolkit",
                session=session,
            )
            return f"超出管理员设置的字数限制: {word_limit}"

        # 先把用户消息构造成记录，暂存内存
        user_rec = cls._build_user_record(
            format_usr_msg(username, session, message), img_url
        )
        round_records: list[dict] = [user_rec]
        # 拿到当前历史（含 system prompt），发送给模型
        result = await cls.get_zhipu_result(
            uid,
            ChatConfig.get("CHAT_MODEL"),
            (await cls.get_chat_history(uid)) + round_records,
            session,
        )

        # 内容审查 / 输入违规
        if result.error_code == 1:
            logger.info(
                f"USERNAME `{username}` 问题: {message} ---- 触发内容审查",
                "zhipu_toolkit",
                session=session,
            )
            # 不写入任何历史，直接返回提示
            return result.content  # pyright: ignore[reportReturnType]

        # 模型内部错误
        if result.error_code == 2:
            logger.error(
                f"获取结果失败 e:{result.content}", "zhipu_toolkit", session=session
            )
            return f"出错了: {result.content}"

        # 不应出现的情况：message 为空
        if result.message is None:
            logger.error(
                f"Missing result.message for uid: {uid}, returning error."
                f"Result content: {result.content}"
            )
            return f"出错了: {result.content}"

        if result.content and await is_harmful_output(
            msg.extract_plain_text(), result.content
        ):
            logger.warning(
                f"UID {uid} 用户试图套取人设: 封禁用户 {session.user.id} 5 分钟",  # noqa: E501
                "zhipu_toolkit",
                session=session,
            )
            await BanConsole.ban(
                session.user.id,
                None,
                9999,
                "试图套取人设",
                300,
            )
            return ChatConfig.get("BLOCK_TIP")

        # 模型第一次回复（可能带 tool_calls），先暂存
        round_records.append(cls._build_assistant_record(result.message))

        max_tool_calls = max(0, int(ChatConfig.get("MAX_TOOL_CALLS_PER_TURN")))
        result = await cls._resolve_tool_chain(
            uid, session, round_records, max_tool_calls, result
        )
        if result.error_code != 0 or result.message is None:
            logger.error(
                f"工具链处理失败: {result.content}",
                "zhipu_toolkit",
                session=session,
            )
            return f"出错了: {result.content}"

        # 到这里，整轮对话都是“结构正常”的，可以一次性写入 DB + 缓存
        await cls._flush_round_history(uid, round_records)

        answer = extract_message_content(result.content)
        logger.info(
            f"USERNAME `{username}` 问题：{message} ---- 回答：{answer}",
            "zhipu_toolkit",
            session=session,
        )
        return answer

    @classmethod
    async def clear_history(cls, uid: str | None = None) -> int:
        """清理历史记录，并同步清空内存缓存。"""
        _history_cache.clear(uid)
        return await ZhipuChatHistory.clear_history(uid)

    @classmethod
    async def get_chat_history(cls, uid: str) -> list[dict]:
        """统一获取对话历史的入口，带内存缓存 + TTL。

        行为:
            - 若缓存中存在并且在 TTL 内，则直接返回缓存中的历史；
            - 否则从数据库加载最近若干条记录，写入缓存并返回。
        """
        if cached_history := _history_cache.get(uid):
            return [
                {
                    "role": "system",
                    "content": await get_prompt(),
                },
                *cached_history,
            ]

        # 缓存不存在或已过期，从数据库获取完整历史
        history = await ZhipuChatHistory.get_history(uid)
        _history_cache.set(uid, history)
        return [
            {
                "role": "system",
                "content": await get_prompt(),
            },
            *history,
        ]

    @classmethod
    async def call_impersonation_ai(cls, session: Uninfo):
        gid = session.scene.id

        rows = (
            await ChatHistory.filter(group_id=gid, bot_id=session.self_id)
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
            parts.append(f"{r['create_time']} [{uname}]({r['user_id']}): {r['text']}")
        CHAT_RECORDS = "\n\n".join(parts)

        # .format(
        #     date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #     name=BotConfig.self_nickname,
        #     uid=session.self_id,
        # )
        result = await cls.get_zhipu_result(
            uid=get_request_id(),
            model=ChatConfig.get("IMPERSONATION_MODEL"),
            messages=[
                {
                    "role": "system",
                    "content": IMPERSONATION_PROMPT,
                },
                {"role": "user", "content": CHAT_RECORDS},
            ],
            session=session,
            impersonation=True,
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
        if not answer:
            logger.warning("伪人发生空回复异常", "zhipu_toolkit", session=session)
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
        session: Uninfo,
        impersonation: bool = False,
        use_tool: bool = True,
    ) -> ZhipuResult:
        loop = asyncio.get_event_loop()
        client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
        request_id = get_request_id()
        tools = ToolsManager.get_tools() if use_tool else None
        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=model,
                    messages=messages,
                    user_id=uid,
                    request_id=request_id,
                    tools=tools,
                    thinking={"type": "disabled"},
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
                        None,
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
        cls, session: Uninfo, tool_call: CompletionMessageToolCall
    ):
        if not tool_call:
            return None

        args = tool_call.function.arguments
        logger.info(
            f"调用工具 {tool_call.function.name}",
            "zhipu_toolkit",
            session=session,
        )
        return await ToolsManager.call_func(session, tool_call.function.name, args)


class ImpersonationStatus:
    @classmethod
    async def check(cls, session: Uninfo) -> bool:
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
