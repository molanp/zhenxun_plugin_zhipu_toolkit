import asyncio
import datetime
import os
from pathlib import Path
import random

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
)

# ==== 简单的内存缓存，用于减少 normal_chat 频繁扫数据库 ====

# 每个 uid 的对话缓存：
#   uid -> { "last_access": datetime, "data": list[dict] }
_CHAT_HISTORY_CACHE: dict[str, dict] = {}
# 缓存有效期：多久没有访问就认为过期，自动丢弃
CHAT_HISTORY_TTL_SECONDS = 30 * 60  # 30 分钟
# 每个 uid 最多保留多少条历史记录，防止内存无限增长
CHAT_HISTORY_MAX_LEN = 200


def _prune_history_cache() -> None:
    """清理超过 TTL 未访问的缓存，避免内存常驻过多 uid。"""
    if not _CHAT_HISTORY_CACHE:
        return
    now = datetime.datetime.now()
    to_delete = []
    for uid, info in _CHAT_HISTORY_CACHE.items():
        last_access: datetime.datetime = info.get("last_access", now)
        if (now - last_access).total_seconds() > CHAT_HISTORY_TTL_SECONDS:
            to_delete.append(uid)
    for uid in to_delete:
        _CHAT_HISTORY_CACHE.pop(uid, None)
    if to_delete:
        logger.debug(
            f"normal_chat 缓存清理: 移除 {len(to_delete)} 个 uid 的历史缓存",
            "zhipu_toolkit",
        )


@scheduler.scheduled_job("interval", minutes=20, id="zhipu_normal_chat_cache_prune")
async def _prune_history_cache_job() -> None:
    """定时任务：周期性清理 normal_chat 的内存缓存."""
    _prune_history_cache()


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
                return

            elif response.task_status == "FAIL":
                await action.send(Text("生成失败了。"), reply_to=True)
                return

            await asyncio.sleep(2)

        except Exception as e:
            raise e


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
        now = datetime.datetime.now()
        cache_info = _CHAT_HISTORY_CACHE.get(uid)
        if cache_info is None:
            # 让下一次 get_chat_history 从 DB 重新加载即可
            return

        history: list = cache_info.get("data", [])
        # 这里 history 的结构是 get_history 返回的那种形式：
        # {"role":..., "content":(str or list[mix]),"tool_call_id":..., "tool_calls":...}  # noqa: E501
        for rec in records:
            if rec.get("res_url"):
                content = [
                    {"type": "text", "text": rec["content"]},
                    {
                        "type": "image_url",
                        "image_url": {"url": rec["res_url"]},
                    },
                ]
            else:
                content = rec["content"]
            history.append(
                {
                    "role": rec["role"],
                    "content": content,
                    "tool_call_id": rec.get("tool_call_id"),
                    "tool_calls": rec.get("tool_calls"),
                }
            )
        cache_info["data"] = history[-CHAT_HISTORY_MAX_LEN:]
        cache_info["last_access"] = now

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
            uid, ChatConfig.get("CHAT_MODEL"), await cls.get_chat_history(uid), session
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

        # 模型第一次回复（可能带 tool_calls），先暂存
        round_records.append(cls._build_assistant_record(result.message))

        # 工具调用：执行成功则增加 tool 记录 + 第二次模型回复
        tool_result = await cls.parse_function_call(
            uid, session, result.message.tool_calls
        )
        if tool_result and result.message.tool_calls:
            # 工具执行结果记为 tool 角色的一条记录
            first_tool_call = result.message.tool_calls[0]
            round_records.append(
                cls._build_tool_record(tool_result, first_tool_call.id)
            )

            # 带工具结果，再次调用模型
            result = await cls.get_zhipu_result(
                uid,
                ChatConfig.get("CHAT_MODEL"),
                await cls.get_chat_history(uid),
                session,
                use_tool=False,
            )

            # 这里也只在返回结构正常时才追加到 round_records
            if result.error_code != 0 or result.message is None:
                logger.error(
                    f"工具链第二次调用模型失败: {result.content}",
                    "zhipu_toolkit",
                    session=session,
                )
                return f"出错了: {result.content}"

            round_records.append(cls._build_assistant_record(result.message))

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
        if uid is None:
            _CHAT_HISTORY_CACHE.clear()
        else:
            _CHAT_HISTORY_CACHE.pop(uid, None)
        return await ZhipuChatHistory.clear_history(uid)

    @classmethod
    async def get_chat_history(cls, uid: str) -> list[dict]:
        """统一获取对话历史的入口，带内存缓存 + TTL。

        行为:
            - 若缓存中存在并且在 TTL 内，则直接返回缓存中的历史；
            - 否则从数据库加载最近若干条记录，写入缓存并返回。
        """
        now = datetime.datetime.now()
        if cache_info := _CHAT_HISTORY_CACHE.get(uid):
            last_access: datetime.datetime = cache_info.get("last_access", now)
            if (now - last_access).total_seconds() <= CHAT_HISTORY_TTL_SECONDS:
                # 缓存有效，更新访问时间并返回
                cache_info["last_access"] = now
                data: list = cache_info.get("data", [])
                data.insert(0, {"role": "system", "content": await get_prompt()})
                return data

        # 缓存不存在或已过期，从数据库获取完整历史
        history = await ZhipuChatHistory.get_history(uid)
        # 写入缓存，截断长度避免无限增长
        _CHAT_HISTORY_CACHE[uid] = {
            "last_access": now,
            "data": history[-CHAT_HISTORY_MAX_LEN:],
        }
        history.insert(0, {"role": "system", "content": await get_prompt()})
        return history

    @classmethod
    async def call_impersonation_ai(cls, session: Uninfo):
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
        session: Uninfo,
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
        session: Uninfo,
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
                return await ToolsManager.call_func(
                    session, tool_call.function.name, args
                )
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
