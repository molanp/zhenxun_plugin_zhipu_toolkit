from nonebot_plugin_uninfo import Uninfo

from ..utils.QQApi import QQApi
from .AbstractTool import AbstractTool


class QQZoneTool(AbstractTool):
    def __init__(self):
        super().__init__(
            name="qqZoneTool",
            description=(
                "这是一个可以实现你发送或者删除qq空间说说的工具，当你觉得对话很有趣或者值"
                "得记录的时候可以调用实现发送说说(对话时主动调用可以稍微积极一些)，用户明"
                "确提出删除qq空间说说时你可以调用该工具删除说说，但是用户主动提出发送说说"
                "时你不能调用(发送说说只能你自己觉的可以调用时再主动调用)"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": (
                            "你将要发送到qq空间说说的内容(以发送者的角度生成流畅通顺的内容)"
                        ),
                    },
                    "type": {
                        "type": "boolean",
                        "description": "是否是删除说说",
                        "default": False,
                    },
                    "pos": {
                        "type": "number",
                        "description": "删除第几个说说",
                        "default": 1,
                    },
                },
                "required": ["text"],
            },
        )

    async def func(
        self, session: Uninfo, text: str = "", type: bool = False, pos: int = 1
    ):
        if not type:
            try:
                if not text:
                    return "发送说说失败，没有要发送的内容"
                result = await QQApi(session).setQzone(text)
                if result["code"] != 0:
                    return f"❎ 说说发表失败\n{result}"
                return f"✅ 说说发表成功，内容：\n{result['content']}"
            except Exception as e:
                return f"发送说说失败，{e}"
        else:
            if not pos:
                return "❎ 请描述要删除第几个说说"
            # 获取说说列表
            _list = await QQApi(session).getQzone(1, pos - 1)

            if "msglist" not in _list:
                return "❎ 未获取到该说说"
            # 要删除的说说
            domain = _list["msglist"][0]
            # 请求接口
            result = await QQApi(session).delQzone(domain["tid"], domain["t1_source"])
            if not result:
                return "❎删除说说失败"
            return (
                "✅ 删除说说成功：\n"
                f"{pos}.{domain['content']}\n"
                f" - [{'私密' if domain['secret'] else '公开'}]"
                f"{domain['cmtnum']} 条评论"
            )
