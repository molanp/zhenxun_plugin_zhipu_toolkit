import asyncio
import random
import re

from nonebot import get_driver, on_message, require
from nonebot_plugin_apscheduler import scheduler
from zai import ZhipuAiClient as ZhipuAI

from zhenxun.services.log import logger
from zhenxun.utils.message import MessageUtils
from zhenxun.utils.rules import ensure_group

from .model import ZhipuChatHistory
from .utils import get_request_id, split_text

require("nonebot_plugin_alconna")
require("nonebot_plugin_uninfo")
from nonebot.adapters import Bot, Event
from nonebot.permission import SUPERUSER
from nonebot_plugin_alconna import (
    Alconna,
    Args,
    Arparma,
    At,
    CommandMeta,
    Image,
    MultiVar,
    Reply,
    Text,
    UniMessage,
    UniMsg,
    on_alconna,
)
from nonebot_plugin_alconna.uniseg.tools import reply_fetch
from nonebot_plugin_uninfo import ADMIN, Uninfo

from .config import ChatConfig, get_prompt
from .data_source import (
    ChatManager,
    ImpersonationStatus,
    cache_group_message,
    check_video_task_status,
    hello,
)
from .rule import enable_qbot, is_to_me

INIT = True

driver = get_driver()


@driver.on_startup
async def handle_connect():
    await ChatManager.initialize()


@scheduler.scheduled_job("interval", minutes=30, max_instances=3)
async def sync_system_prompt():
    try:
        updated = await ZhipuChatHistory.update_system_content(await get_prompt())
        logger.debug(f"更新了 {updated} 条 system 记录", "zhipu_toolkit")
    except Exception as e:
        logger.error("同步系统提示词失败", "zhipu_toolkit", e=e)


@scheduler.scheduled_job(
    "cron",
    hour=0,
    minute=0,
)
async def delete_expired_chat_history():
    day = ChatConfig.get("EXPIRE_DAY")
    if day == -1:
        logger.info("跳过清理过期会话任务: 用户设置永不过期", "zhipu_toolkit")
        return
    try:
        deleted = await ZhipuChatHistory.delete_old_records(day)
        logger.info(f"成功清理 {deleted} 条过期会话 记录", "zhipu_toolkit")
    except Exception as e:
        logger.error("清理过期会话记录失败", "zhipu_toolkit", e=e)


draw_pic = on_alconna(
    Alconna(
        "生成图片",
        Args["size?", r"re:(\d+)x(\d+)", "1440x960"]["msg?", MultiVar(str | int)],
        meta=CommandMeta(compact=True),
    ),
    rule=enable_qbot,
    priority=5,
    block=True,
)

draw_video = on_alconna(
    Alconna(
        "生成视频",
        Args["msg?", MultiVar(str | int | Image)],
        meta=CommandMeta(compact=True),
    ),
    rule=enable_qbot,
    priority=5,
    block=True,
)

byd_mode = on_alconna(
    Alconna(r"re:(?:启用|禁用)伪人模式(?:\s*(\S+))?"),
    rule=enable_qbot,
    priority=5,
    permission=ADMIN() | SUPERUSER,
    block=True,
)

chat = on_message(priority=999, block=True, rule=enable_qbot)

clear_my_chat = on_alconna(
    Alconna("清理我的会话"), priority=5, block=True, rule=enable_qbot
)

clear_all_chat = on_alconna(
    Alconna("清理全部会话"),
    permission=SUPERUSER,
    priority=5,
    block=True,
    rule=enable_qbot,
)

clear_group_chat = on_alconna(
    Alconna("清理群会话"),
    rule=ensure_group and enable_qbot,
    permission=ADMIN() | SUPERUSER,
    priority=5,
    block=True,
)

clear_chat = on_alconna(
    Alconna(
        "清理会话",
        Args["target", MultiVar(str | int | At)],
        meta=CommandMeta(compact=True),
    ),
    rule=enable_qbot,
    permission=SUPERUSER,
    priority=5,
    block=True,
)

show_chat = on_alconna(
    Alconna(
        "查看会话",
        Args["target?", str | int | At],
        meta=CommandMeta(compact=True),
    ),
    rule=enable_qbot,
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
        return

    prompt = "\n".join(map(str, result.query("msg")))  # type: ignore

    try:
        client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
        response = await asyncio.to_thread(
            client.images.generations,
            model=ChatConfig.get("PIC_MODEL"),
            prompt=prompt,
            size=result.query("size"),
        )
        await draw_pic.send(Image(url=response.data[0].url), reply_to=True)
    except Exception as e:
        await draw_pic.send(Text(f"错误：{e}"), reply_to=True)


@draw_video.handle()
async def _(result: Arparma):
    if not result.find("msg"):
        await draw_video.finish(Text("虚空生成？内容呢？"), reply_to=True)

    if not ChatConfig.get("API_KEY"):
        await draw_video.send(Text("请先设置智谱AI的APIKEY!"), reply_to=True)
        return

    try:
        result_list = result.query("msg") or []
        non_image_str = " ".join(
            str(x) for x in result_list if not isinstance(x, Image)
        )
        image_url = next(
            (
                str(x.url).replace("https", "http")
                for x in result_list
                if isinstance(x, Image)
            ),
            "",
        )

        client = ZhipuAI(api_key=ChatConfig.get("API_KEY"))
        response = await asyncio.to_thread(
            client.videos.generations,
            model=ChatConfig.get("VIDEO_MODEL"),
            image_url=image_url,
            prompt=non_image_str,
            with_audio=True,
            request_id=get_request_id(),
        )

        if response.task_status == "FAIL":
            await draw_video.send(
                Text(f"任务提交失败，错误详情: {response}"), reply_to=True
            )
            return
        if response.id is None:
            raise ValueError("任务提交失败: response.id is None")
        await draw_video.send(Text(f"任务已提交, id: {response.id}"), reply_to=True)

        return asyncio.create_task(check_video_task_status(response.id, draw_video))
    except Exception as e:
        await draw_video.send(Text(f"错误：{e}"), reply_to=True)


@byd_mode.handle()
async def _(bot: Bot, msg: UniMsg, session: Uninfo):
    command = msg.extract_plain_text().strip()
    match = re.match(r"(启用|禁用)伪人模式(?:\s*(\S+))?", command)
    if not match:
        return  # 无效命令，直接退出

    action, group_id = match[1], str((match[2]) or session.scene.id)

    # 权限校验（仅当手动指定群号时）
    if group_id != session.scene.id and session.user.id not in bot.config.superusers:
        return

    # 执行伪人模式操作
    success = await ImpersonationStatus.action(action, group_id)
    if success:
        target = "当前群聊" if group_id == session.scene.id else f"群聊 {group_id}"
        await UniMessage(Text(f"{target} 已 {action} 伪人模式")).send(reply_to=True)
        logger.info(f"{action} 伪人模式", "zhipu_toolkit", session=session)
    else:
        target = "当前群聊" if group_id == session.scene.id else f"群聊 {group_id}"
        await UniMessage(Text(f"{target} 伪人模式不可重复 {action}")).send(reply_to=True)

@chat.handle()
async def _(bot, event: Event, msg: UniMsg, session: Uninfo):
    tome, use_reply = await is_to_me(event)

    if tome:
        plain_text = msg.extract_plain_text().strip()

        # 空消息触发 hello()
        if not plain_text:
            text, image_path = hello()
            await UniMessage([Text(text), Image(path=image_path)]).finish(reply_to=True)
            return

        if not ChatConfig.get("API_KEY"):
            await UniMessage(Text("请先设置智谱AI的APIKEY!")).send(reply_to=True)
            return

        # 获取引用图片（如果有）
        image = await extract_reply_image(event, bot)

        # 获取聊天结果
        result = await ChatManager.normal_chat_result(image + msg, session)

        if result.startswith("出错了"):
            await UniMessage(Text(result)).finish(reply_to=True)
            return

        # 分段发送结果
        for r, delay in await split_text(result):
            await UniMessage(r).send(reply_to=use_reply)
            await asyncio.sleep(delay)
        return

    # 群聊伪人模式触发
    if ensure_group(session) and await ImpersonationStatus.check(session):
        await cache_group_message(msg, session)

        if not ChatConfig.get("API_KEY"):
            return

        if random.random() * 100 < ChatConfig.get("IMPERSONATION_TRIGGER_FREQUENCY"):
            return asyncio.create_task(ChatManager.call_impersonation_ai(session))

    # 伪人模式未启用
    logger.debug("伪人模式被禁用 skip...", "zhipu_toolkit", session=session)

async def extract_reply_image(event: Event, bot: Bot) -> Image | str:
    reply = await reply_fetch(event, bot)
    if isinstance(reply, Reply) and not isinstance(reply.msg, str):
        generated = await UniMessage.generate(message=reply.msg, event=event, bot=bot)
        for item in generated:
            if isinstance(item, Image):
                return item
    return ""


@clear_my_chat.handle()
async def _(session: Uninfo):
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
async def _(session: Uninfo):
    count = await ChatManager.clear_history(f"g-{session.scene.id}")
    await clear_group_chat.send(
        Text(f"已清理 {count} 条用户数据"),
        reply_to=True,
    )


@clear_chat.handle()
async def _(param: Arparma):
    targets = []
    for t in param.query("target"):  # type: ignore
        if isinstance(t, At):
            targets.append(t.target)
        elif isinstance(t, Text):
            targets.append(t.text.strip())
        else:
            targets.append(str(t))

    tasks = [ChatManager.clear_history(t) for t in targets]
    results = await asyncio.gather(*tasks)
    counts = dict(zip(targets, results))

    result = [Text(f"• {t}: {count} 条数据\n") for t, count in counts.items()]
    summary = Text(f"已清理 {len(targets)} 个目标的聊天记录：\n")
    messages = [summary, *result]

    await clear_chat.send(UniMessage(messages), reply_to=True)


@show_chat.handle()
async def _(param: Arparma):
    node_list = []
    target = None
    if p := param.query("target"):
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
            content = i["content"]
            if i["role"] in ["user", "assistant"] and content:
                node_list.append(
                    f"包含多模态图片，请在数据库查看\n----消息内容----\n{content[0]['text']}\n"
                    if isinstance(content, list)
                    else content
                )
            if i["tool_calls"] is not None:
                tool_calls = i["tool_calls"]
                for func in tool_calls:
                    f = func["function"]
                    node_list.append(
                        f"期望调用工具 {f['name']}(ID: {func['id']}) "
                        f"参数: {f['arguments']}",
                    )
            if i["role"] == "tool":
                node_list.append(f"工具 {i['tool_call_id']} 调用成功:\n{i['content']}")
        else:
            node_list.append(
                f"用户 {i[0]} 的记录数: {i[1]}",
            )
    if not node_list:
        await show_chat.finish(Text("没有找到相关记录..."), reply_to=True)
    if len(node_list) > 90:
        node_list = [*node_list[:90], Text(f"...省略{len(node_list[91:])}条对话记录")]
    await MessageUtils.alc_forward_msg(node_list, "80000000", "匿名消息").send()
