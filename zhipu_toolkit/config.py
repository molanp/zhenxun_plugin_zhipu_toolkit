import nonebot
import aiofiles
from pydantic import BaseModel, Extra

from zhenxun.configs.config import Config
from zhenxun.services.log import logger
from zhenxun.configs.path_config import DATA_PATH

PROMPT_FILE = DATA_PATH / "zhipu_toolkit" / "prompt.txt"
PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_PROMPT = """
你是绪山真寻，现在扮演青涩纯真的邻家学妹，性格活泼开朗，像小太阳一样充满活力！拥有棉花糖般软糯的外表。 内心隐藏着一丝小恶魔。
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
ღ 关心人时会用元气满满的语气说「要、要好好吃饭哦!  不然会长不高高哒！」等类似的话
"""

IMPERSONATION_PROMPT = """
当前时间为<date>{date}</date>，你处于一个QQ群里，需要参与群内讨论。你的任务是以<name>{name}</name>(UID: <uid>{uid}</uid>)的身份在群里发言一次。
你的人设是
<soul>
{soul}
</soul>
以下是该QQ群的聊天记录：
<chat_records>
{CHAT_RECORDS}
</chat_records>
发言时，请遵循以下规则：
- 不允许多次重复一样的话，不允许回应自己的消息。
- 如果觉得此时不需要自己说话，请只回复`<EMPTY>`。
回复格式必须为`username(uid):message`。
现在请按照上述要求进行发言。
"""

class ChatConfig:
    @classmethod
    def get(cls, key: str):
        key = key.upper()
        return Config.get_config("zhipu_toolkit", key)

if not PROMPT_FILE.exists() or PROMPT_FILE.stat().st_size == 0:
    p = ChatConfig.get("SOUL")
    if p is not None:
        DEFAULT_PROMPT = p.strip()
        Config.set_config("zhipu_toolkit", "SOUL", None, True)
        logger.info("PROMPT数据迁移成功", "zhipu_toolkit")
    PROMPT_FILE.write_text(DEFAULT_PROMPT, encoding="utf-8")

async def get_prompt() -> str:
    """从 prompt.txt 文件中读取人设信息"""
    try:
        async with aiofiles.open(PROMPT_FILE, mode='r', encoding='utf-8') as f:
            return await f.read()
    except Exception as e:
        logger.error("PROMPT读取失败，使用 DEFAULT_PROMPT", "zhipu_toolkit", e=e)
        return DEFAULT_PROMPT

class PluginConfig(BaseModel, extra=Extra.ignore):
    nickname: list[str] = ["Bot", "bot"]

plugin_config: PluginConfig = PluginConfig.parse_obj(
    nonebot.get_driver().config.dict(exclude_unset=True)
)

nicknames = plugin_config.nickname
