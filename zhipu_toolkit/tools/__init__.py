import inspect
from typing import Any

from nonebot_plugin_uninfo import Uninfo
import ujson

from zhenxun.services.log import logger

from .registry import registry


class ToolsManager:
    @classmethod
    async def init(cls, disable_tools: list[str] | None = None) -> None:
        """Initialize the tools registry by loading all tool modules."""
        await registry.load_modules(disable_tools)

    @staticmethod
    def get_tools() -> list[dict[str, Any]]:
        """Return the tools registry."""
        return [t.to_schema() for t in registry.get_tools()]

    @staticmethod
    async def call_func(session: Uninfo, name: str, args: Any) -> str:
        """Call the function of the specified tool."""
        descriptor = registry.get_tool(name)
        if descriptor is None:
            return "Tool is not found in the registry."

        func = descriptor.func
        sig = inspect.signature(func)
        parameters = sig.parameters

        if isinstance(args, str):
            try:
                kwargs = ujson.loads(args)
            except Exception as e:
                return f"Invalid arguments format: {e}"
        elif isinstance(args, dict):
            kwargs = args
        else:
            return "Tool arguments must be a JSON string or a dict."

        if "session" in parameters:
            kwargs["session"] = session

        try:
            return await func(**kwargs)
        except TypeError as e:
            logger.error("参数类型错误", "zhipu_toolkit.tools", e=e)
            return "参数数量不符"
        except Exception as e:
            logger.error(f"调用工具 {name} 失败", "zhipu_toolkit.tools", e=e)
            return f"{type(e)},{e}"

    @classmethod
    async def reload_tools(cls) -> None:
        """Reload all tool modules."""
        await registry.reload()

    @classmethod
    async def reflash_tools(cls) -> None:
        """Reflash all tool modules list."""
        await registry.reload()
