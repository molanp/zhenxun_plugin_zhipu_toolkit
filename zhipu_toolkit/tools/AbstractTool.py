from typing import Any

from pydantic import BaseModel, Field


class AbstractTool(BaseModel):
    name: str = Field(default="")
    """工具名称"""
    parameters: dict[str, Any] = Field(default_factory=dict)
    """符合 JSON Schema 的参数定义"""
    description: str = Field(default="")
    """工具描述"""

    def to_dict(self):
        if "type" not in self.parameters:
            self.parameters["type"] = "object"
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    async def func(self, session: Any, *args: Any, **kwargs: Any) -> Any:
        """由工具类实现的调用逻辑"""
        raise NotImplementedError("工具函数必须实现")
