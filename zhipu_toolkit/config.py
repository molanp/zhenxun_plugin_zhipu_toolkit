import nonebot
from pydantic import BaseModel, Extra

from zhenxun.configs.config import Config


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
