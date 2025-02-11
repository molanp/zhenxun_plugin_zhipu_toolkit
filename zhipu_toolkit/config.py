from typing import ClassVar

import nonebot
from pydantic import BaseModel, Extra

from zhenxun.configs.config import Config


class ChatConfig:
    default: ClassVar[dict] = {
        "API_KEY": "",
        "CHAT_MODEL": "glm-4-flash",
        "PIC_MODEL": "cogview-3-flash",
        "VIDEO_MODEL": "cogvideox-flash",
        "IMAGE_UNDERSTANDING_MODEL": "glm-4v-flash",
        "SOUL": "你是真寻，你强大且无所不能",
        "CHAT_MODE": "user",
        "IMPERSONATION_MODE": False,
        "IMPERSONATION_TRIGGER_FREQUENCY": 20,
        "IMPERSONATION_MODEL": "glm-4-flash",
        "IMPERSONATION_SOUL": False
    }

    @classmethod
    def get(cls, key: str):
        key = key.upper()
        return Config.get_config("zhipu_toolkit", key, cls.default.get(key))


class PluginConfig(BaseModel, extra=Extra.ignore):
    nickname: list[str] = ["Bot", "bot"]


plugin_config: PluginConfig = PluginConfig.parse_obj(
    nonebot.get_driver().config.dict(exclude_unset=True)
)

nicknames = plugin_config.nickname
