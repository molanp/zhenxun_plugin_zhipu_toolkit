from datetime import datetime, timedelta
from typing import Any, ClassVar

from pydantic import BaseModel
from tortoise import fields
from tortoise.functions import Count
from tortoise.transactions import in_transaction
from tortoise.validators import Validator
from zhipuai.types.chat.chat_completion import CompletionMessage

from zhenxun.services.db_context import Model


class GroupMessageModel(BaseModel):
    uid: str
    """用户ID"""
    username: str
    """用户昵称"""
    msg: str
    """消息内容"""
    time: str
    """消息时间"""


class ZhipuResult(BaseModel):
    content: str | None = None
    error_code: int
    message: CompletionMessage | None = None


class RoleValidator(Validator):
    def __call__(self, value: str):
        if value not in ["system", "user", "assistant", "tool"]:
            raise ValueError("Invalid role")


class ZhipuChatHistory(Model):
    id = fields.IntField(pk=True, generated=True, auto_increment=True)
    """自增id"""
    uid = fields.CharField(255, description="用户唯一标识符（类型+用户ID组合）")
    """用户id"""
    role = fields.CharField(
        16, description="消息的角色信息", validators=[RoleValidator()]
    )
    """消息的角色信息"""
    finish_reason = fields.TextField(
        description="模型推理终止的原因", null=True, default=None
    )
    """模型推理终止的原因"""
    content = fields.TextField(null=True, default=None)
    """对话内容"""
    tool_calls: list[dict[str, Any]] | None = fields.JSONField(null=True, default=None)  # type: ignore
    """模型生成的应调用的函数名称和参数"""
    tool_call_id: str | None = fields.TextField(null=True, default=None)  # type: ignore
    """工具调用的记录"""
    create_time = fields.DatetimeField(auto_now_add=True)
    """创建时间"""

    class Meta:  # pyright: ignore [reportIncompatibleVariableOverride]
        table = "zhipu_chat_history"
        table_description = "智谱对话历史表"
        indexes: ClassVar = [("uid",)]

    @classmethod
    async def clear_history(cls, uid: str | None = None) -> int:
        async with in_transaction():
            return (
                await cls.filter(uid=uid).delete() if uid else await cls.all().delete()
            )

    @classmethod
    async def get_history(cls, uid: str) -> list[dict]:
        """
        获取指定用户的所有对话记录

        :param uid: 用户唯一标识符
        :return: 包含所有历史记录的字典列表，格式示例：
        ```
            [{
                "uid": "user_id",
                "role": "user",
                "content": "你好",
                "create_time": "2023-07-01 12:00:00"
                ...
            }]
        ```
        """
        records = await cls.filter(uid=uid).order_by("id").all()
        return [
            {
                "role": record.role,
                "content": record.content,
                "finish_reason": record.finish_reason,
                "tool_calls": record.tool_calls,
                "tool_call_id": record.tool_call_id,
            }
            for record in records
        ]

    @classmethod
    async def update_system_content(cls, content: str, uid: str | None = None) -> int:
        query = cls.filter(role="system")
        if uid:
            query = query.filter(uid=uid)
        return await query.update(content=content)

    @classmethod
    async def get_user_list(cls) -> list[tuple[str, int]]:
        """获取所有用户的uid及其记录数量（元组列表形式）"""
        results = (
            await cls.all()
            .annotate(record_count=Count("id"))
            .group_by("uid")
            .values("uid", "record_count")
        )
        return [(item["uid"], item["record_count"]) for item in results]

    @classmethod
    async def delete_latest_record(cls, uid: str) -> int:
        """删除指定用户的最新一条记录"""
        latest_record = await cls.filter(uid=uid).order_by("-id").first()
        if latest_record:
            await latest_record.delete()
            return 1
        return 0

    @classmethod
    async def delete_old_records(cls, days: int) -> int:
        """删除 n 天前的所有记录"""
        cutoff = datetime.now() - timedelta(days=days)

        async with in_transaction():
            deleted = await cls.filter(create_time__lt=cutoff).delete()

        return deleted
