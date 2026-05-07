from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AbstractTool(ABC):
    name: str
    """工具名称"""
    parameters: dict[str, Any]
    """符合 JSON Schema 的参数定义"""
    description: str
    """工具描述"""

    @abstractmethod
    async def func(self, session: Any, *args: Any, **kwargs: Any) -> str:
        """由工具类实现的调用逻辑"""

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
