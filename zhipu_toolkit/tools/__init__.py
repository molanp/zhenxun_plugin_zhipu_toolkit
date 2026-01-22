import asyncio
import importlib
import inspect
import pkgutil
from typing import Any, ClassVar

from nonebot_plugin_uninfo import Uninfo
import ujson

from zhenxun.services.log import logger

from .AbstractTool import AbstractTool


class ToolsManager:
    tools_registry: ClassVar[dict[str, AbstractTool]] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def init(cls) -> None:
        """Initialize the tools registry by loading all tool modules."""
        async with cls._lock:
            if cls.tools_registry:
                return  # Avoid re-initializing if already done

            await cls._load_modules()

    @classmethod
    async def get_tools(cls) -> list[dict[str, Any]] | None:
        """Return the tools registry."""
        await cls.init()
        if not cls.tools_registry:
            return
        return [
            {"type": "function", "function": tool.to_dict()}
            for tool in cls.tools_registry.values()
        ]

    @classmethod
    async def call_func(cls, session: Uninfo, name: str, args: str) -> Any:
        """Call the function of the specified tool."""
        await cls.init()
        tool = cls.tools_registry.get(name)
        if tool is None:
            raise ValueError(f"Tool '{name}' not found in the registry.")

        func = tool.func
        sig = inspect.signature(func)
        parameters = sig.parameters

        try:
            kwargs = ujson.loads(args)
        except Exception as e:
            raise ValueError(f"Invalid arguments format: {e}") from e
        if "session" in parameters:
            kwargs["session"] = session

        try:
            return await func(**kwargs)
        except TypeError as e:
            logger.error("参数类型错误", e=e)
            raise
        except Exception as e:
            logger.error(f"调用工具 {name} 失败", e=e)
            return f"调用工具失败: {type(e)},{e}"

    @classmethod
    async def reload_tools(cls) -> None:
        """Reload all tool modules."""
        async with cls._lock:
            for module_info in pkgutil.iter_modules(__path__):
                module_name = module_info.name
                module = importlib.import_module(f".{module_name}", package=__name__)
                importlib.reload(module)

    @classmethod
    async def reflash_tools(cls) -> None:
        """Reflash all tool modules list."""
        async with cls._lock:
            cls.tools_registry.clear()
            await cls._load_modules()

    @classmethod
    async def _load_modules(cls) -> None:
        """Load or reload tool modules and register tools."""
        if not __path__:
            logger.warning("Module path is empty.")
            return

        for module_info in pkgutil.iter_modules(__path__):
            module_name = module_info.name
            module = importlib.import_module(f".{module_name}", package=__name__)

            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, AbstractTool)
                    and obj is not AbstractTool
                ):
                    instance = obj()
                    cls.tools_registry[instance.name] = instance
