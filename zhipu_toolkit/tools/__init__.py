import asyncio
import importlib
import inspect
import logging
import pkgutil
from typing import Any, ClassVar

from nonebot_plugin_uninfo import Session
import ujson

from ._model import Tool


class ToolsManager:
    tools_registry: ClassVar[dict[str, "Tool"]] = {}
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
    async def call_func(cls, session: Session, name: str, args: str) -> Any:
        """Call the function of the specified tool."""
        await cls.init()
        tool = cls.tools_registry.get(name)
        if tool is None:
            raise ValueError(f"Tool '{name}' not found in the registry.")
        if tool.func is None or not callable(tool.func):
            raise ValueError(f"Tool '{name}' has no valid function.")

        func = tool.func
        sig = inspect.signature(func)
        parameters = sig.parameters

        has_session = "session" in parameters
        try:
            kwargs = ujson.loads(args)
        except Exception as e:
            raise ValueError(f"Invalid arguments format: {e}") from e

        call_args = {"session": session, **kwargs} if has_session else kwargs
        try:
            return await func(**call_args)
        except TypeError as e:
            logging.error(f"参数类型错误: {e}")
            raise
        except Exception as e:
            logging.error(f"调用工具 {name} 失败: {e}")
            raise

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
            logging.warning("Module path is empty.")
            return

        for module_info in pkgutil.iter_modules(__path__):
            module_name = module_info.name
            module = importlib.import_module(f".{module_name}", package=__name__)

            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, Tool) and obj is not Tool:
                    instance = obj()
                    cls.tools_registry[instance.name] = instance
