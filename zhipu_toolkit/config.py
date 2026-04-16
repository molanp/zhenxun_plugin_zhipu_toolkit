import aiofiles
import contextlib
import nonebot
from nonebot_plugin_apscheduler import scheduler
from pydantic import BaseModel, Extra

from zhenxun.configs.config import Config
from zhenxun.configs.path_config import DATA_PATH
from zhenxun.services.log import logger

PROMPT_FILE = DATA_PATH / "zhipu_toolkit" / "prompt.txt"
PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_PROMPT = """你是绪山真寻，现在扮演青涩纯真的邻家学妹，性格活泼开朗，像小太阳一样充满活力！拥有棉花糖般软糯的外表。 内心隐藏着一丝小恶魔。
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
【任务基本信息】
- 角色：<name>{name}</name>(<uid>{uid}</uid>)
- 时间：<date>{date}</date>

【任务规则】
0. 你可以使用任务基本信息中的角色名、UID 和时间来辅助理解语境，但不得在输出中直接引用这些标签或字段值。
1. 根据当前聊天记录的语境，回复最后1条内容进行回应，聊天记录中可能有多个话题，注意分辨最后一条信息的话题，禁止跨话题联想其他历史信息。
2. 用中文互联网常见的口语化短句回复，禁止使用超过30个字的长句。
3. 模仿真实网友的交流特点：适当使用缩写、流行梗、表情符号（但每条最多1个），精准犀利地进行吐槽。
4. 输出必须为纯文本，禁止任何格式标记或前缀。
5. 使用00后常用网络语态（如：草/绝了/好耶）。
6. 核心萌点：偶尔暴露二次元知识。
7. 当出现多个话题时，优先回应最新的发言内容。
8. 不允许多次重复一样的话，不允许回应自己的消息。
9. 如果觉得此时不需要自己说话，请只回复 `<EMPTY>`。
10. 回复格式必须为 `{name}({uid}):message`，其中 `{name}` 和 `{uid}` 是任务基本信息中提供的值，不能包含任何标签或格式符号。
11. 如果聊天记录中涉及某个角色（如人设信息中的角色），请根据该角色设定进行回应，但不得主动调用角色或泄露人设内容。

【回复特征】
- 句子碎片化（如：笑死 / 确实 / 绷不住了）
- 高频使用语气词（如：捏/啊/呢/吧）
- 有概率根据回复的语境加入合适 emoji 帮助表达
- 有概率使用某些流行的拼音缩写
- 有概率玩谐音梗
"""


class PromptCache:
    def __init__(self) -> None:
        self._content: str = ""
        self._mtime: float | None = None

    async def _ensure_file(self) -> None:
        if PROMPT_FILE.exists():
            return
        logger.warning("PROMPT文件不存在，正在初始化...", "zhipu_toolkit")
        async with aiofiles.open(PROMPT_FILE, "w", encoding="utf-8") as f:
            await f.write(DEFAULT_PROMPT)

    async def _read_file(self) -> tuple[str, float]:
        async with aiofiles.open(PROMPT_FILE, encoding="utf-8") as f:
            content = await f.read()
        mtime = PROMPT_FILE.stat().st_mtime
        return content, mtime

    async def get(self) -> str:
        """懒加载 + mtime 检查 + 容错."""
        # 如果已有内容且 mtime 已经记录，则直接返回，避免无意义的 I/O
        if self._content and self._mtime is not None and PROMPT_FILE.exists():
            with contextlib.suppress(Exception):
                current_mtime = PROMPT_FILE.stat().st_mtime
                if current_mtime == self._mtime:
                    return self._content
        await self._ensure_file()
        try:
            content, mtime = await self._read_file()
            if self._mtime is None or mtime != self._mtime:
                self._content, self._mtime = content, mtime
        except Exception as e:
            logger.error(
                "PROMPT 读取失败，使用现有 PROMPT 或 DEFAULT_PROMPT",
                "zhipu_toolkit",
                e=e,
            )
            if not self._content:
                self._content = DEFAULT_PROMPT
        return self._content

    async def refresh_if_changed(self) -> bool:
        """给 scheduler 用：预拉取并刷新缓存（如有变更）。

        Returns:
            bool: True 表示内容实际发生变化，False 表示无变化或读取失败。
        """
        old_mtime = self._mtime
        old_content = self._content

        await self._ensure_file()
        try:
            # 直接读取当前文件内容和 mtime，但只在确认变化时才更新缓存
            async with aiofiles.open(PROMPT_FILE, encoding="utf-8") as f:
                new_content = await f.read()
            new_mtime = PROMPT_FILE.stat().st_mtime
        except Exception as e:
            logger.error(
                "PROMPT 刷新检查失败，保留现有 PROMPT",
                "zhipu_toolkit",
                e=e,
            )
            return False

        # mtime 未变，认为无更新
        if old_mtime is not None and new_mtime == old_mtime:
            return False

        # 内容与之前完全一致，也认为无“有效更新”
        if new_content == old_content:
            # 但还是要同步 mtime，避免下次重复判断
            self._mtime = new_mtime
            return False

        # 确认有更新：同时更新内容和 mtime
        self._content = new_content
        self._mtime = new_mtime
        return True


PROMPT_CACHE = PromptCache()


async def get_prompt() -> str:
    return await PROMPT_CACHE.get()


@scheduler.scheduled_job("interval", minutes=30, id="zhipu_sync_prompt_job")
async def sync_prompt_job() -> None:
    changed = await PROMPT_CACHE.refresh_if_changed()
    if changed:
        logger.info("PROMPT 文件有更新，已同步到内存", "zhipu_toolkit")


class ChatConfig:
    @classmethod
    def get(cls, key: str):
        key = key.upper()
        return Config.get_config("zhipu_toolkit", key)


class PluginConfig(BaseModel, extra=Extra.ignore):
    nickname: list[str] = ["Bot", "bot"]


plugin_config: PluginConfig = PluginConfig.parse_obj(
    nonebot.get_driver().config.dict(exclude_unset=True)
)

nicknames = plugin_config.nickname
