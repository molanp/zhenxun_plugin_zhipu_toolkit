from zhipuai import ZhipuAI

from zhenxun.configs.config import Config

api_key = Config.get_config("zhipu_toolkit", "API_KEY", "")
soul = Config.get_config("zhipu_toolkit", "SOUL", "你是真寻，你强大且无所不能")
client = ZhipuAI(api_key=api_key)
