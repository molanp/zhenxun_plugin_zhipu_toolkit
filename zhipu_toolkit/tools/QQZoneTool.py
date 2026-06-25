from ..utils.QQApi import QQApi
from .AbstractTool import AbstractTool
from nonebot_plugin_uninfo import Uninfo


class PostQzoneTool(AbstractTool):
    """发布QQ空间说说的工具"""

    name = "postQzoneTool"
    description = (
        "防刷与合规工具。仅在用户明确要求发布、发送、创作QQ空间说说或动态时调用。"
        "你必须以第一人称视角将用户的意思转化为流畅的动态文本。日常正常闲聊绝对禁止调用此工具。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "说说文本内容。必须以第一人称视角生成，严禁留空或编写无意义内容。",
            },
        },
        "required": ["text"],
    }

    async def func(self, session: Uninfo, text: str) -> str:
        if not text:
            return "error: missing_text_content_for_posting"
        try:
            result = await QQApi(session).setQzone(text)
            if result["code"] != 0:
                return f"error: platform_rejected_post, result: {result}"
            return f"success: post_created_successfully, content: {result['content']}"
        except Exception as e:
            return f"error: post_failed_exception: {e!s}"


class DeleteQzoneTool(AbstractTool):
    """删除QQ空间说说的工具"""

    name = "deleteQzoneTool"
    description = (
        "高危敏感操作工具。仅在用户明确发出删除、清空特定QQ空间说说或动态的指令时调用。"
        "日常闲聊、吐槽或未明确表达删除意图时绝对禁止调用。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "pos": {
                "type": "number",
                "description": "代表要删除的说说序号（倒数第几个）。必须根据用户指令中的具体数字确定，若用户未指定具体数字则默认传 1。",
                "default": 1,
            },
        },
        "required": [],
    }

    async def func(self, session: Uninfo, pos: int = 1) -> str:
        if pos < 1:
            return "error: invalid_position_index"
        try:
            _list = await QQApi(session).getQzone(1, pos - 1)
            if "msglist" not in _list or not _list["msglist"]:
                return f"error: no_talk_found_at_position_{pos}"
            domain = _list["msglist"][0]
            result = await QQApi(session).delQzone(domain["tid"], domain["t1_source"])
            if not result:
                return "error: platform_rejected_deletion"
            is_secret = "true" if domain["secret"] else "false"
            return (
                f"success: talk_deleted_successfully, position: {pos}, "
                f"deleted_content_preview: {domain['content']}, "
                f"is_secret: {is_secret}, comment_count: {domain['cmtnum']}"
            )
        except Exception as e:
            return f"error: delete_failed_exception: {e!s}"
