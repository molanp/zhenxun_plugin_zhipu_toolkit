import nonebot
from pydantic import BaseModel, Extra
from pathlib import Path
from typing import Set

from zhenxun.configs.config import Config

class ChatConfig:
   default = {
      "API_KEY": "",
      "CHAT_MODEL": "glm-4-flash",
      "PIC_MODEL": "cogview-3-flash",
      "VIDEO_MODEL": "cogvideox-flash",
      "SOUL": "你是真寻，你强大且无所不能"
   }
   @classmethod
   def get(cls, key: str):
      key = key.upper()
      return Config.get_config(
         "zhipu_toolkit",
         key,
         cls.default.get(key)
      )


class PluginConfig(BaseModel, extra=Extra.ignore):
    nickname: Set[str] = ["Bot", "bot"]

plugin_config: PluginConfig = PluginConfig.parse_obj(nonebot.get_driver().config.dict(exclude_unset=True))

nicknames = plugin_config.nickname
