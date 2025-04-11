import asyncio
import random
import re
from typing import Any

from arclet.alconna import Alconna, AllParam, Args, CommandMeta
from nonebot import get_driver, on_message, require
from nonebot_plugin_apscheduler import scheduler
from zhipuai import ZhipuAI

from zhenxun.configs.config import BotConfig
from zhenxun.services.log import logger
from zhenxun.utils.message import MessageUtils
from zhenxun.utils.rules import ensure_group

from .model import ZhipuChatHistory
from .utils import get_username, split_text

require("nonebot_plugin_alconna")
from nonebot.adapters import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    Arparma,
    At,
    CommandMeta,
    CustomNode,
    Image,
    Text,
    UniMessage,
    UniMsg,
    on_alconna,
)
from nonebot_plugin_uninfo import ADMIN, Session, Uninfo, UniSession

from .config import ChatConfig
from .data_source import (
    ChatManager,
    ImpersonationStatus,
    cache_group_message,
    check_task_status_periodically,
    hello,
    submit_task_to_zhipuai,
)
from .rule import is_to_me

driver = get_driver()


@driver.on_startup
async def handle_connect():
    await ChatManager.initialize()


@scheduler.scheduled_job(
    "interval",
    minutes=5,
)
async def sync_system_prompt():
    try:
        updated = await ZhipuChatHistory.update_system_content(ChatConfig.get("SOUL"))
        logger.debug(f"更新了 {updated} 条 system 记录", "zhipu_toolkit")
    except Exception as e:
        logger.error("同步系统提示词失败", "zhipu_toolkit", e=e)


draw_pic = on_alconna(
    Alconna(
        "生成图片",
        Args["size?", r"re:(\d+)x(\d+)", "1440x960"]["msg?", AllParam],
        meta=CommandMeta(compact=True),
    ),
    priority=5,
    block=True,
)

draw_video = on_alconna(
    Alconna("生成视频", Args["msg?", AllParam], meta=CommandMeta(compact=True)),
    priority=5,
    block=True,
)

byd_mode = on_alconna(
    Alconna("re:(启用|禁用)伪人模式\s*(\d*)"),
    priority=5,
    permission=ADMIN() | SUPERUSER,
    block=True,
)

chat = on_message(priority=999, block=True)

clear_my_chat = on_alconna(
   Alconna("清理我的会话"),
   priority=5, block=True)

clear_all_chat = on_alconna(
    Alconna("清理全部会话"), permission=SUPERUSER, priority=5, block=True
)

clear_group_chat = on_alconna(
    Alconna("清理群会话"),
    rule=ensure_group,
    permission=ADMIN() | SUPERUSER,
    priority=5,
    block=True,
)

clear_chat = on_alconna(
    Alconna("清理会话", Args["target", AllParam], meta=CommandMeta(compact=True)),
    permission=ADMIN() | SUPERUSER,
    priority=5,
    block=True,
)

show_chat = on_alconna(
    Alconna("查看会话", Args["target?", Any], meta=CommandMeta(compact=True)),
    permission=ADMIN() | SUPERUSER,
    priority=5,
    block=True,
)


@draw_pic.handle()
async def _(result: Arparma):
    if not result.find("msg"):
        await draw_pic.finish(Text("虚空绘画？内容呢？"), reply_to=True)
    if ChatConfig.get("API_KEY") == "":
        await draw_pic.send(Text("请先设置智谱AI的APIKEY!"), reply_to=True)
    else:
        try:
            loop = asyncio.get_running_loop()
            client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
            response = await loop.run_in_executor(
                None,
                lambda: client.images.generations(
                    model=ChatConfig.get("PIC_MODEL"),
                    prompt="".join(map(str, result.query("msg"))),  # type: ignore
                    size=result.query("size"),
                ),
            )
            await draw_pic.send(Image(url=response.data[0].url), reply_to=True)
        except Exception as e:
            await draw_pic.send(Text(f"错了：{e}"), reply_to=True)


@draw_video.handle()
async def _(result: Arparma):
    if not result.find("msg"):
        await draw_video.finish(Text("虚空生成？内容呢？"), reply_to=True)
    if ChatConfig.get("API_KEY") == "":
        await draw_video.send(Text("请先设置智谱AI的APIKEY!"), reply_to=True)
    else:
        try:
            result_list = result.query("msg")
            non_image_str = "".join(
                str(x)
                for x in result_list  # type: ignore
                if not isinstance(x, Image)  # type: ignore
            )
            image_url = next(
                (
                    x.url.replace("https", "http")  # type: ignore
                    for x in result_list  # type: ignore
                    if isinstance(x, Image)
                ),
                "",
            )
            response = await submit_task_to_zhipuai(non_image_str, image_url)
        except Exception as e:
            await draw_video.send(Text(str(e)))
        else:
            if response.task_status != "FAIL":
                await draw_video.send(
                    Text(f"任务已提交,id: {response.id}"), reply_to=True
                )
                asyncio.create_task(  # noqa: RUF006
                    check_task_status_periodically(response.id, draw_video)  # type: ignore
                )
            else:
                await draw_video.send(
                    Text(f"任务提交失败，e:{response}"), reply_to=True
                )


@byd_mode.handle()
async def _(bot: Bot, msg: UniMsg, session: Session = UniSession()):
    command = msg.extract_plain_text().strip()
    if match := re.match(r"(启用|禁用)伪人模式(?:\s*(\d+))?", command):
        action = match[1]
        if group_id := match[2]:
            if session.user.id not in bot.config.superusers:
                return

            if await ImpersonationStatus.action(action, int(group_id)):
                await UniMessage(Text(f"群聊 {group_id} 已 {action} 伪人模式")).send(
                    reply_to=True
                )
                logger.info(f"{action} 伪人模式", "zhipu_toolkit", session=session)
            else:
                await UniMessage(
                    Text(f"群聊 {group_id} 伪人模式不可重复 {action}")
                ).send(reply_to=True)
        elif ensure_group(session):
            if await ImpersonationStatus.action(action, session.scene.id):
                await UniMessage(Text(f"当前群聊已 {action} 伪人模式")).send(
                    reply_to=True
                )
                logger.info(f"{action} 伪人模式", "zhipu_toolkit", session=session)
            else:
                await UniMessage(Text(f"当前群聊伪人模式不可重复 {action}")).send(
                    reply_to=True
                )


@chat.handle()
async def zhipu_chat(event: Event, msg: UniMsg, session: Session = UniSession()):
    tome, reply = await is_to_me(event)
    if tome:
        if msg.only(Text) and msg.extract_plain_text().strip() == "":
            result = await hello()
            await UniMessage([Text(result[0]), Image(path=result[1])]).finish(
                reply_to=True
            )
        if ChatConfig.get("API_KEY") == "":
            await UniMessage(Text("请先设置智谱AI的APIKEY!")).send(reply_to=True)
            return
        result = await ChatManager.normal_chat_result(msg, session)
        for r, delay in await split_text(result):
            await UniMessage(r).send(reply_to=reply)
            await cache_group_message(UniMessage(r), session, BotConfig.self_nickname)
            await asyncio.sleep(delay)
    elif ensure_group(session) and await ImpersonationStatus.check(session):
        if ChatConfig.get("API_KEY") == "":
            return
        await cache_group_message(msg, session)
        if random.random() * 100 < ChatConfig.get("IMPERSONATION_TRIGGER_FREQUENCY"):
            result = await ChatManager.impersonation_result(session)
            if result:
                await UniMessage(result).send()
                await cache_group_message(
                    UniMessage(result),
                    session,
                    BotConfig.self_nickname,
                )
    else:
        logger.debug("伪人模式被禁用 skip...", "zhipu_toolkit", session=session)


@clear_my_chat.handle()
async def _(session: Session = UniSession()):
    uid = session.user.id
    await clear_my_chat.send(
        Text(f"已清理 {uid} 的 {await ChatManager.clear_history(uid)} 条数据"),
        reply_to=True,
    )


@clear_all_chat.handle()
async def _():
    await clear_all_chat.send(
        Text(f"已清理 {await ChatManager.clear_history()} 条用户数据"),
        reply_to=True,
    )


@clear_group_chat.handle()
async def _(session: Session = UniSession()):
    count = await ChatManager.clear_history(f"g-{session.scene.id}")
    await clear_group_chat.send(
        Text(f"已清理 {count} 条用户数据"),
        reply_to=True,
    )


@clear_chat.handle()
async def _(param: Arparma):
    targets = [
        str(p.target) if isinstance(p, At) else p.text.strip()
        for p in param.query("target")  # type: ignore
        if (isinstance(p, At) or (isinstance(p, Text) and p.text.strip()))
    ]

    tasks = [ChatManager.clear_history(t) for t in targets]
    results = await asyncio.gather(*tasks)
    counts = dict(zip(targets, results))

    result = [Text(f"• {t}: {count} 条数据\n") for t, count in counts.items()]
    summary = Text(f"已清理 {len(targets)} 个目标的聊天记录：\n")
    messages = [summary, *result]

    await clear_chat.send(UniMessage(messages), reply_to=True)


@show_chat.handle()
async def _(session: Uninfo, param: Arparma):
    node_list = []
    target = None
    if p := param.query("target"):
        logger.info(str(type(p)), "zhipu_toolkit")
        if isinstance(p, At):
            target = str(p.target)
        elif isinstance(p, Text):
            target = p.text.strip()
        else:
            target = str(p)

    if target is None:
        data = await ZhipuChatHistory.get_user_list()
    else:
        data = await ZhipuChatHistory.get_history(target)
    for i in data:
        if isinstance(i, dict):
            assert isinstance(target, str)
            if i["role"] in ["user", "assistant"]:
                node_list.append(
                    i["content"],
                )
        else:
            node_list.append(
                f"用户 {i[0]} 的记录数: {i[1]}",
            )
    await MessageUtils.alc_forward_msg(
        node_list,
        target or session.self_id,
        await get_username(target or session.self_id, session),
    ).send(reply_to=True)
