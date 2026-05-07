import asyncio
import inspect
from typing import Any

from nonebot_plugin_uninfo import Uninfo
import ujson

from zhenxun.services.log import logger

from .registry import ToolRegistry


class ToolsManager:
    registry: type[ToolRegistry] = ToolRegistry
    _lock = asyncio.Lock()

    @classmethod
    async def init(cls, disable_tools: list[str] = []) -> None:
        """Initialize the tools registry by loading all tool modules."""
        async with cls._lock:
            await cls.registry.load_modules()
            cls.registry.disable_tools(disable_tools)

    @classmethod
    def get_tools(cls) -> list[dict[str, Any]] | None:
        """Return the tools registry."""
        if tools := cls.registry.get_tools():
            return [tool.to_schema() for tool in tools]
        else:
            return

    @classmethod
    async def call_func(cls, session: Uninfo, name: str, args: Any) -> str:
        """Call the function of the specified tool."""
        descriptor = cls.registry.get_tool(name)
        if descriptor is None:
            raise ValueError(f"Tool '{name}' not found in the registry.")

        func = descriptor.instance.func
        sig = inspect.signature(func)
        parameters = sig.parameters

        if isinstance(args, str):
            try:
                kwargs = ujson.loads(args)
            except Exception as e:
                raise ValueError(f"Invalid arguments format: {e}") from e
        elif isinstance(args, dict):
            kwargs = args
        else:
            raise ValueError("Tool arguments must be a JSON string or a dict.")

        if "session" in parameters:
            kwargs["session"] = session

        try:
            return await func(**kwargs)
        except TypeError as e:
            logger.error("参数类型错误", "zhipu_toolkit.tools", e=e)
            return "调用工具失败: 参数数量不符"
        except Exception as e:
            logger.error(f"调用工具 {name} 失败", "zhipu_toolkit.tools", e=e)
            return f"调用工具失败: {type(e)},{e}"

    @classmethod
    async def reload_tools(cls) -> None:
        """Reload all tool modules."""
        async with cls._lock:
            await cls.registry.reload()

    @classmethod
    async def reflash_tools(cls) -> None:
        """Reflash all tool modules list."""
        async with cls._lock:
            cls.registry.clear()
            await cls.registry.load_modules()
