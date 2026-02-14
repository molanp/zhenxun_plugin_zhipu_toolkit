from typing import Any


class AbstractTool:
    name: str
    """工具名称"""
    parameters: dict[str, Any]
    """符合 JSON Schema 的参数定义"""
    description: str
    """工具描述"""

    async def func(self, session: Any, *args: Any, **kwargs: Any) -> str:
        """由工具类实现的调用逻辑"""
        raise NotImplementedError("工具函数必须实现")
