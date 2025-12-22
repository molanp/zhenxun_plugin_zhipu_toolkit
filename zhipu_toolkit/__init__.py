from nonebot.plugin import PluginMetadata

from zhenxun.configs.config import BotConfig
from zhenxun.configs.utils import PluginExtraData, RegisterConfig

from .handler import INIT as INIT

__plugin_meta__ = PluginMetadata(
    name="AI全家桶",
    description="AI全家桶，一次安装，到处使用，省时省力省心",
    usage=f"""
    AI全家桶，一次安装，到处使用，省时省力省心
    usage:
        生成图片 (可选size) <prompt>
        生成视频 (可选基于生成内容图片) <prompt>
        清理我的会话:   用于清理你与AI的聊天记录
        清理群会话: (仅管理员)用于清理本群的大杂烩记录，仅当分组模式为group时生效
        启用/禁用伪人模式: (仅管理员)开启或关闭当前群聊的伪人模式
    或者与机器人聊天，{BotConfig.self_nickname}是可以看懂大家的表情包和链接的...
    例如；
        @Bot 抱抱
        {BotConfig.self_nickname}老婆
    """.strip(),
    extra=PluginExtraData(
        author="molanp",
        version="3.2",
        menu_type="群内小游戏",
        superuser_help="""
        超级管理员额外命令
        格式:
            查看会话 ?user : 查看指定user的会话记录或全部会话列表
            清理会话 @user / uid : 用于清理指定用户的会话记录,支持多个目标
            清理全部会话: 清理Bot缓存的全部会话记录
            启用/禁用伪人模式 群号: 开启或关闭指定群聊的伪人模式，空格是可选的
        """,
        configs=[
            RegisterConfig(
                key="API_KEY",
                value=None,
                type=str,
                help="智谱AI平台的APIKEY",
                default_value="",
            ),
            RegisterConfig(
                key="CHAT_MODEL",
                value="glm-4.5-flash",
                type=str,
                help="所使用的对话模型",
                default_value="glm-4-flash",
            ),
            RegisterConfig(
                key="IS_MULTIMODAL",
                value=False,
                type=bool,
                help="对话模型是否为多模态模型，启用后忽略图像理解模型配置项",
                default_value=False,
            ),
            RegisterConfig(
                key="PIC_MODEL",
                value="cogview-3-flash",
                type=str,
                help="所使用的图片生成模型",
                default_value="cogview-3-flash",
            ),
            RegisterConfig(
                key="VIDEO_MODEL",
                value="cogvideox-flash",
                type=str,
                help="所使用的视频生成模型",
                default_value="cogvideox-flash",
            ),
            RegisterConfig(
                key="IMAGE_UNDERSTANDING_MODEL",
                value="glm-4v-flash",
                type=str,
                help="所使用的图像理解模型",
                default_value="glm-4v-flash",
            ),
            RegisterConfig(
                key="CHAT_MODE",
                value="user",
                type=str,
                help="对话分组模式，支持'user','group','all'",
                default_value="user",
            ),
            RegisterConfig(
                key="IMPERSONATION_MODE",
                value=False,
                type=bool,
                help="是否启用伪人模式",
                default_value=False,
            ),
            RegisterConfig(
                key="IMPERSONATION_TRIGGER_FREQUENCY",
                value=20,
                type=float,
                help="伪人模式触发频率[0-100]",
                default_value=20,
            ),
            RegisterConfig(
                key="IMPERSONATION_MODEL",
                value="glm-4-flash",
                type=str,
                help="伪人模式对话模型，建议使用免费模型",
                default_value="glm-4-flash",
            ),
            RegisterConfig(
                key="IMPERSONATION_BAN_GROUP",
                value=[],
                type=list[str],
                help="禁用伪人模式的群组列表",
                default_value=[],
            ),
            RegisterConfig(
                key="EXPIRE_DAY",
                value=3,
                type=int,
                help="用户对话记录保存时间(天), -1表示永久保存",
                default_value=3,
            ),
            RegisterConfig(
                key="WORD_LIMIT",
                value=1000,
                type=int,
                help="单次对话消息字数限制(最大值一般为4095)",
                default_value=1000,
            ),
            RegisterConfig(
                key="TEXT_MAX_SPLIT",
                value=3,
                type=int,
                help="单次对话消息最大分割段数, 0表示无限分割, -1表示不分割",
                default_value=3,
            ),
        ],
    ).dict(),
)
