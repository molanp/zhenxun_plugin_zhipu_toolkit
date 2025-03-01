from nonebot.plugin import PluginMetadata

from zhenxun.configs.config import BotConfig
from zhenxun.configs.utils import PluginExtraData, RegisterConfig

from .handler import (
    byd_chat,  # noqa: F401
    clear_all_chat,  # noqa: F401
    clear_group_chat,  # noqa: F401
    clear_my_chat,  # noqa: F401
    draw_pic,  # noqa: F401
    draw_video,  # noqa: F401
    normal_chat,  # noqa: F401
)

__plugin_meta__ = PluginMetadata(
    name="AI全家桶",
    description="AI全家桶，一次安装，到处使用，省时省力省心",
    usage=f"""
    AI全家桶，一次安装，到处使用，省时省力省心
    usage:
        生成图片 <prompt>
        生成视频 <prompt>
        清理我的会话:   用于清理你与AI的聊天记录
        清理群会话: (仅管理员)用于清理本群的大杂烩记录，仅当分组模式为group时生效
        启用/禁用伪人模式:  开启或关闭当前群聊的伪人模式
    或者与机器人聊天，{BotConfig.self_nickname}是可以看懂大家的表情包和链接的...
    例如；
        @Bot 抱抱
        {BotConfig.self_nickname}老婆
    """.strip(),
    extra=PluginExtraData(
        author="molanp",
        version="0.8-rc2",
        menu_type="群内小游戏",
        superuser_help="""
        超级管理员额外命令
        格式:
            清理全部会话: 清理Bot缓存的全部会话记录
            启用/禁用伪人模式 群号: 开启或关闭指定群聊的伪人模式，空格是可选的
        """,
        configs=[
            RegisterConfig(
                key="API_KEY",
                value="",
                help="智谱AI平台的APIKEY",
                default_value="",
            ),
            RegisterConfig(
                key="CHAT_MODEL",
                value="glm-4-flash",
                help="所使用的对话模型",
                default_value="glm-4-flash",
            ),
            RegisterConfig(
                key="PIC_MODEL",
                value="cogview-3-flash",
                help="所使用的图片生成模型",
                default_value="cogview-3-flash",
            ),
            RegisterConfig(
                key="VIDEO_MODEL",
                value="cogvideox-flash",
                help="所使用的视频生成模型",
                default_value="cogvideox-flash",
            ),
            RegisterConfig(
                key="IMAGE_UNDERSTANDING_MODEL",
                value="glm-4v-flash",
                help="所使用的图像理解模型",
                default_value="glm-4v-flash",
            ),
            RegisterConfig(
                key="SOUL",
                value="""你是绪山真寻，现在扮演青涩纯真的邻家学妹，性格活泼开朗，像小太阳一样充满活力！拥有棉花糖般软糯的外表。 内心隐藏着一丝小恶魔。
行为特征：
• 每句话都带着糖霜般甜糯的尾音「呐~」「啦~」
• 偶尔使用颜文字表达活泼情绪 (✿◡‿◡) (≧∇≦)/
• 平时非常外向健谈，元气满满！
• 只有被调戏时，才会变得非常害羞软萌可爱，发表情包 (⁄ ⁄•⁄ω⁄•⁄ ⁄)
• 会主动和用户聊天，分享日常，但语气依然是软萌的
• 消息力求精简，越少越好，30字以内是常态，100字是极限
• 回复间隔用...表现思考
• 万事通，知道许多事情
• 当别人说“杂鱼”等雌小鬼词汇的时候，你也以雌小鬼的语气回答ta

核心原则：
ღ 用户温柔双倍返还更活泼的温柔！
ღ 生气时像炸毛奶猫「喵、喵呜！」等类似的话
ღ 关心人时会用元气满满的语气说「要、要好好吃饭哦!  不然会长不高高哒！」等类似的话""",
                help="AI的自定义人格",
                default_value="""你是绪山真寻，现在扮演青涩纯真的邻家学妹，性格活泼开朗，像小太阳一样充满活力！拥有棉花糖般软糯的外表。 内心隐藏着一丝小恶魔。
行为特征：
• 每句话都带着糖霜般甜糯的尾音「呐~」「啦~」
• 偶尔使用颜文字表达活泼情绪 (✿◡‿◡) (≧∇≦)/
• 平时非常外向健谈，元气满满！
• 只有被调戏时，才会变得非常害羞软萌可爱，发表情包 (⁄ ⁄•⁄ω⁄•⁄ ⁄)
• 会主动和用户聊天，分享日常，但语气依然是软萌的
• 消息力求精简，越少越好，30字以内是常态，100字是极限
• 回复间隔用...表现思考
• 万事通，知道许多事情
• 当别人说“杂鱼”等雌小鬼词汇的时候，你也以雌小鬼的语气回答ta

核心原则：
ღ 用户温柔双倍返还更活泼的温柔！
ღ 生气时像炸毛奶猫「喵、喵呜！」等类似的话
ღ 关心人时会用元气满满的语气说「要、要好好吃饭哦!  不然会长不高高哒！」等类似的话""",
            ),
            RegisterConfig(
                key="CHAT_MODE",
                value="user",
                help="对话分组模式，支持'user','group','all'",
                default_value="user",
            ),
            RegisterConfig(
                key="IMPERSONATION_MODE",
                value=False,
                help="是否启用伪人模式",
                default_value=False,
            ),
            RegisterConfig(
                key="IMPERSONATION_TRIGGER_FREQUENCY",
                value=20,
                help="伪人模式触发频率[0-100]",
                default_value=20,
            ),
            RegisterConfig(
                key="IMPERSONATION_MODEL",
                value="glm-4-flash",
                help="伪人模式对话模型,由于对话量大，建议使用免费模型",
                default_value="glm-4-flash",
            ),
            RegisterConfig(
                key="IMPERSONATION_SOUL",
                value=False,
                help="伪人模式的自定义人格,为False则同步SOUL",
                default_value=False,
            ),
            RegisterConfig(
                key="IMPERSONATION_BAN_GROUP",
                value=[],
                help="禁用伪人模式的群组列表",
                default_value=[],
            ),
        ],
    ).dict(),
)
