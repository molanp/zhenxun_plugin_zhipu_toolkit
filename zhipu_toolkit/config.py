from zhenxun.configs.config import Config

class ChatConfig:
   default = {
      "API_KEY": "",
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
