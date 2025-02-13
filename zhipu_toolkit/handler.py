import asyncio
import random
import re

from arclet.alconna import Alconna, AllParam, Args, CommandMeta
from nonebot import on_message, on_regex, require
from zhipuai import ZhipuAI

from zhenxun.services.log import logger

require("nonebot_plugin_alconna")
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    Event,
    Message,
    MessageEvent,
    MessageSegment,
)
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.permission import SUPERUSER
from nonebot.rule import is_type
from nonebot_plugin_alconna import Image, Match, Text, on_alconna

from .config import ChatConfig, nicknames
from .data_source import (
    ChatManager,
    ImpersonationStatus,
    cache_group_message,
    check_task_status_periodically,
    submit_task_to_zhipuai,
)


async def is_to_me(event: Event) -> bool:
    msg = event
    .get_message().extract_plain_text()
    for nickname in nicknames:
        if nickname in msg:
            return True
    return event.is_tome()


draw_pic = on_alconna(
    Alconna("生成图片", Args["msg?", AllParam], meta=CommandMeta(compact=True)),
    priority=5,
    block=True,
)

draw_video = on_alconna(
    Alconna("生成视频", Args["message?", AllParam], meta=CommandMeta(compact=True)),
    priority=5,
    block=True,
)

byd_mode = on_regex(
    r"(启用|禁用)伪人模式\s*(?:/\d+)?",
    priority=5,
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
    block=True,
)

normal_chat = on_message(rule=is_to_me, priority=998, block=True)

byd_chat = on_message(rule=is_type(GroupMessageEvent), priority=999, block=False)

clear_my_chat = on_alconna(Alconna("清理我的会话"), priority=5, block=True)

clear_all_chat = on_alconna(
    Alconna("清理全部会话"), permission=SUPERUSER, priority=5, block=True
)

clear_group_chat = on_alconna(
    Alconna("清理群会话"),
    rule=is_type(GroupMessageEvent),
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
    priority=5,
    block=True,
)


@draw_pic.handle()
async def _(msg: Match[str]):
    if msg.available:
        draw_pic.set_path_arg("msg", str(msg.result))


@draw_video.handle()
async def _(message: Match[str]):
    if message.available:
        draw_video.set_path_arg("message", str(message.result))


@byd_mode.handle()
async def _(bot: Bot, event: MessageEvent):
    command = event.get_plaintext()
    if match := re.match(r"(启用|禁用)伪人模式(?:\s*(\d+))?", command):
        action = match[1]
        if group_id := match[2]:
            if not await SUPERUSER(bot, event):
                return

            if await ImpersonationStatus.action(action, int(group_id)):
                await byd_mode.send(
                    MessageSegment.text(f"群聊 {group_id} 已 {action} 伪人模式"),
                    reply_message=True,
                )
                logger.info(
                    f"SUPERUSER {event.user_id} GROUP {group_id} 已{action}伪人模式",
                    "zhipu_toolkit",
                )
            else:
                await byd_mode.send(
                    MessageSegment.text(f"群聊 {group_id} 伪人模式不可重复{action}"),
                    reply_message=True,
                )
        elif isinstance(event, GroupMessageEvent):
            if await ImpersonationStatus.action(action, event.group_id):
                await byd_mode.send(
                    MessageSegment.text(f"当前群聊已 {action} 伪人模式"),
                    reply_message=True,
                )
                logger.info(
                    f"Admin {event.user_id} GROUP {event.group_id} 已{action}伪人模式",
                    "zhipu_toolkit",
                )
            else:
                await byd_mode.send(
                    MessageSegment.text(f"当前群聊伪人模式不可重复{action}"),
                    reply_message=True,
                )


@normal_chat.handle()
async def _(event: MessageEvent):
    if ChatConfig.get("API_KEY") == "":
        await normal_chat.send(
            Message(MessageSegment.text("请先设置智谱AI的APIKEY!")), reply_message=True
        )
    else:
        await normal_chat.send(
            Message(Message(await ChatManager.send_message(event))),
            reply_message=True,
        )


@byd_chat.handle()
async def _(event: GroupMessageEvent, bot: Bot):
    if await ImpersonationStatus.check(event):
        if ChatConfig.get("API_KEY") == "":
            return
        await cache_group_message(event)
        if random.random() * 100 < ChatConfig.get("IMPERSONATION_TRIGGER_FREQUENCY"):
            result = await ChatManager.impersonation_result(event, bot)
            if result:
                await byd_chat.send(Message(result))
    else:
        logger.debug(f"GROUP {event.group_id} 伪人模式被禁用.skip...")


@clear_my_chat.handle()
async def _(event: MessageEvent):
    uid = str(event.sender.user_id)
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
async def _(event: GroupMessageEvent):
    count = await ChatManager.clear_history(f"g-{event.group_id}")
    await clear_group_chat.send(
        Text(f"已清理 {count} 条用户数据"),
        reply_to=True,
    )


@draw_pic.got_path("msg", prompt="你要画什么呢")
async def handle_check(msg: str):
    if ChatConfig.get("API_KEY") == "":
        await draw_pic.send(Text("请先设置智谱AI的APIKEY!"), reply_to=True)
    else:
        try:
            loop = asyncio.get_event_loop()
            client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
            response = await loop.run_in_executor(
                None,
                lambda: client.images.generations(
                    model=ChatConfig.get("PIC_MODEL"), prompt=msg, size="1440x720"
                ),
            )
            await draw_pic.send(Image(url=response.data[0].url), reply_to=True)
        except Exception as e:
            await draw_pic.send(Text(f"错了：{e}"), reply_to=True)


@draw_video.got_path("message", prompt="你要制作什么视频呢")
async def submit_task(message: str):
    if ChatConfig.get("API_KEY") == "":
        await draw_pic.send(Text("请先设置智谱AI的APIKEY!"), reply_to=True)
    else:
        try:
            response = await submit_task_to_zhipuai(message)
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
