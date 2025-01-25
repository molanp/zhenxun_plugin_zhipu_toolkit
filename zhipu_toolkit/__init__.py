from zhipuai import ZhipuAI
from zhenxun.configs.utils import PluginExtraData, RegisterConfig
from zhenxun.configs.config import Config
from arclet.alconna import Args, Alconna
from nonebot.plugin import PluginMetadata
from nonebot import require
import asyncio
require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import on_alconna, Match, Text, Image, Video  # noqa: E402


__plugin_meta__ = PluginMetadata(
    name="AI全家桶",
    description="AI全家桶，省时省力省心",
    usage="""
    AI全家桶，省时省力省心
    usage:
        生成图片 <prompt> 
        生成视频 <prompt>
    """.strip(),
    extra=PluginExtraData(
        author="molanp",
        version="0.1",
        menu_type="群内小游戏",
        configs=[
            RegisterConfig(
                key="API_KEY",
                value="",
                help="智谱AI平台的APIKEY",
                default_value="",
            )
        ],
    ).dict(),
)

api_key = Config.get_config("zhipu_toolkit", "API_KEY", "")

client = ZhipuAI(api_key=api_key)

draw_pic = on_alconna(
    Alconna("生成图片", Args["msg?", str, "all"]),
    priority=5,
    block=True
)

draw_video = on_alconna(
    Alconna("生成视频", Args["message?", str, "all"]),
    priority=5,
    block=True
)

@draw_pic.handle()
async def _(msg: Match[str]):
    if msg.available:
        draw_pic.set_path_arg("msg", msg.result)

@draw_video.handle()
async def _(message: Match[str]):
    if message.available:
        draw_video.set_path_arg("message", message.result)

@draw_pic.got_path("msg", prompt="你要画什么呢")
async def handle_check(msg: str):
    if api_key == "":
        await draw_pic.send(Text("请先设置智谱AI的APIKEY!"), reply_to=True)
    else:
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: client.images.generations(
                    model="cogview-3-flash",
                    prompt=msg,
                    size="1440x720")
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
                await draw_video.send(Text(f"任务已提交,id: {response.id}"), reply_to=True)
                # 启动异步任务检查状态
                asyncio.create_task(
                    check_task_status_periodically(response.id, draw_video))
            else:
                await draw_video.send(Text(f"任务提交失败，e:{response}"), reply_to=True)


async def submit_task_to_zhipuai(message: str):
    return client.videos.generations(
        model="cogvideox-flash",
        prompt=message,
        with_audio=True,
    )


async def check_task_status_periodically(task_id: str, m):
    while True:
        try:
            response = await check_task_status_from_zhipuai(task_id)
        except Exception as e:
            await m.send(Text(str(e)), reply_to=True)
            break
        else:
            if response.task_status == "SUCCESS":
                await m.send(Video(
                    url=response.video_result[0].url))
                break
            elif response.task_status == "FAIL":
                await m.send(Text("生成失败了..", reply_to=True))
            await asyncio.sleep(5)


async def check_task_status_from_zhipuai(task_id: str):
    return client.videos.retrieve_videos_result(id=task_id)
