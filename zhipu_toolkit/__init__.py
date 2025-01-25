from nonebot.plugin import PluginMetadata

from zhenxun.configs.config import BotConfig
from zhenxun.configs.utils import PluginExtraData, RegisterConfig

from .handler import chat, draw_pic, draw_video  # noqa: F401

__plugin_meta__ = PluginMetadata(
    name="AI全家桶",
    description="AI全家桶，一次安装，到处使用，省时省力省心",
    usage=f"""
    AI全家桶，一次安装，到处使用，省时省力省心
    usage:
        生成图片 <prompt>
        生成视频 <prompt>
        清理我的会话:   用于清理你与AI的聊天记录
    或者与机器人聊天，
    例如；
        @Bot抱抱
        {BotConfig.self_nickname}老婆
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
            ),
            RegisterConfig(
                key="SOUL",
                value="你是真寻，你强大且无所不能",
                help="AI的自定义人格",
                default_value="你是真寻，你强大且无所不能",
            )
        ],
    ).dict(),
)
