import asyncio
import inspect
from typing import Any

from nonebot_plugin_uninfo import Uninfo
import ujson

from zhenxun.services.log import logger

from .registry import registry


class ToolsManager:
    _lock = asyncio.Lock()

    @classmethod
    async def init(cls, disable_tools: list[str] | None = None) -> None:
        """Initialize the tools registry by loading all tool modules."""
        disable_tools = disable_tools or [] 
        async with cls._lock:
            await registry.load_modules()
            registry.disable_tools(disable_tools)

    @staticmethod
    def get_tools() -> list[dict[str, Any]]:
        """Return the tools registry."""
        return [t.to_schema() for t in registry.get_tools()]

    @staticmethod
    async def call_func(session: Uninfo, name: str, args: Any) -> str:
        """Call the function of the specified tool."""
        descriptor = registry.get_tool(name)
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
            await registry.reload()

    @classmethod
    async def reflash_tools(cls) -> None:
        """Reflash all tool modules list."""
        async with cls._lock:
            registry.clear()
            await registry.load_modules()
