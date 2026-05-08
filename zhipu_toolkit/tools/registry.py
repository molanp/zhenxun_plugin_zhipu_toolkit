import asyncio
import importlib
import inspect
import pkgutil
from typing import ClassVar

from zhenxun.services.log import logger

from .AbstractTool import AbstractTool


class ToolRegistry:
    _registry: ClassVar[dict[str, AbstractTool]] = {}
    _disabled_tools: ClassVar[set[str]] = set()
    _lock = asyncio.Lock()

    @classmethod
    async def load_modules(cls, disable_tools: list[str] | None = None) -> None:
        async with cls._lock:
            if not cls._registry:
                await cls._load_all_modules()
            if disable_tools:
                cls.apply_disabled(disable_tools)

    @classmethod
    async def _load_all_modules(cls) -> None:
        if not __path__:  # noqa: F821
            logger.warning("Module path is empty.")
            return
        for module_info in pkgutil.iter_modules(__path__):  # noqa: F821
            module_name = module_info.name
            try:
                module = importlib.import_module(f".{module_name}", package=__name__)
            except Exception as e:
                logger.error(
                    f"加载工具模块 {module_name} 失败：{e}",
                    "zhipu_toolkit.tools",
                    e=e,
                )
                continue

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, AbstractTool) and obj is not AbstractTool:
                    cls.register(obj)

    @classmethod
    def apply_disabled(cls, tools: list[str]) -> None:
        cls._disabled_tools.update(tools)
        for tool_name in tools:
            if tool_name in cls._registry:
                del cls._registry[tool_name]
                logger.info(f"已禁用工具 {tool_name}", "zhipu_toolkit.tools")

    @classmethod
    def register(cls, tool_cls: type[AbstractTool]) -> None:
        instance = tool_cls()
        if instance.name in cls._registry:
            logger.warning(
                f"工具 {instance.name} 已存在，忽略重复注册。",
                "zhipu_toolkit.tools",
            )
            return
        if instance.name in cls._disabled_tools:
            logger.info(
                f"工具 {instance.name} 被禁用，跳过注册。",
                "zhipu_toolkit.tools",
            )
            return
        cls._registry[instance.name] = instance

    @classmethod
    def disable_tools(cls, tools: list[str]) -> None:
        cls._disabled_tools.update(tools)
        # 移除已注册的禁用工具
        for tool_name in tools:
            if tool_name in cls._registry:
                del cls._registry[tool_name]
                logger.info(f"已禁用工具 {tool_name}", "zhipu_toolkit.tools")

    @classmethod
    def get_tool(cls, name: str) -> AbstractTool | None:
        return cls._registry.get(name)

    @classmethod
    def get_tools(cls) -> list[AbstractTool]:
        return list(cls._registry.values())

    @classmethod
    def clear(cls) -> None:
        cls._registry.clear()

    @classmethod
    async def reload(cls, disable_tools: list[str] | None = None) -> None:
        async with cls._lock:
            cls.clear()
            cls._disabled_tools.clear()
            await cls._load_all_modules()
            if disable_tools:
                cls.apply_disabled(disable_tools)


def register_tool(tool_cls: type[AbstractTool]) -> type[AbstractTool]:
    ToolRegistry.register(tool_cls)
    return tool_cls


registry = ToolRegistry()
