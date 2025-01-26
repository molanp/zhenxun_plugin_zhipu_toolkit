import asyncio

from arclet.alconna import Alconna, Args
from nonebot import on_message, require

require("nonebot_plugin_alconna")
from nonebot.adapters.onebot.v11 import Event, Message, MessageSegment
from nonebot.rule import to_me
from nonebot_plugin_alconna import Image, Match, Text, on_alconna

from .config import api_key, client
from .data_source import (
    ChatManager,
    check_task_status_periodically,
    submit_task_to_zhipuai,
    hello
)

draw_pic = on_alconna(Alconna("生成图片", Args["msg?", str]), priority=5, block=True)

draw_video = on_alconna(
    Alconna("生成视频", Args["message?", str]), priority=5, block=True
)

chat = on_message(rule=to_me(), priority=999, block=True)

clear_my_chat = on_alconna(Alconna("清理我的会话"), priority=5, block=True)


@draw_pic.handle()
async def _(msg: Match[str]):
    if msg.available:
        draw_pic.set_path_arg("msg", msg.result)


@draw_video.handle()
async def _(message: Match[str]):
    if message.available:
        draw_video.set_path_arg("message", message.result)


@chat.handle()
async def _(event: Event):
    if api_key == "":
        await chat.send(
            Message(MessageSegment.text("请先设置智谱AI的APIKEY!")), at_sender=True
        )
    else:
        user_id = event.get_user_id()
        message = event.get_plaintext()
        if message is None or message == "":
           result = await hello()
           await chat.send(
              Message([
                 MessageSegment.text(result[0]),
                 MessageSegment.image(result[1])
              ]),
              at_sender=True
           )
        else:
           await chat.send(
               Message(
                   MessageSegment.text(
                       await ChatManager.send_message(message, int(user_id))
                   )
               ),
               at_sender=True,
           )


@clear_my_chat.handle()
async def _(event: Event):
    uid = int(event.get_user_id())
    await clear_my_chat.send(
        Text(f"已清理 {uid} 的 {await ChatManager.clear_history(uid)} 条数据")
    )


@draw_pic.got_path("msg", prompt="你要画什么呢")
async def handle_check(msg: str):
    if api_key == "":
        await draw_pic.send(Text("请先设置智谱AI的APIKEY!"), reply_to=True)
    else:
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.images.generations(
                    model="cogview-3-flash", prompt=msg, size="1440x720"
                ),
            )
            await draw_pic.send(Image(url=response.data[0].url), reply_to=True)
        except Exception as e:
            await draw_pic.send(Text(f"错了：{e}"), reply_to=True)


@draw_video.got_path("message", prompt="你要制作什么视频呢")
async def submit_task(message: str):
    if api_key == "":
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
                )  # type: ignore
            else:
                await draw_video.send(
                    Text(f"任务提交失败，e:{response}"), reply_to=True
                )
