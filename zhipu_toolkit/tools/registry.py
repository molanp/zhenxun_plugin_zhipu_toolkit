from __future__ import annotations

import asyncio
from dataclasses import dataclass
import importlib
import inspect
from pathlib import Path
import pkgutil
from typing import Any, ClassVar

from zhenxun.services.log import logger

from .AbstractTool import AbstractTool


@dataclass
class ToolDescriptor:
    instance: AbstractTool

    @property
    def name(self) -> str:
        return self.instance.name

    @property
    def description(self) -> str:
        return self.instance.description

    @property
    def parameters(self) -> dict[str, Any]:
        return self.instance.parameters

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    _registry: ClassVar[dict[str, ToolDescriptor]] = {}
    _disabled_tools: ClassVar[set[str]] = set()
    _lock = asyncio.Lock()

    @classmethod
    async def load_modules(cls, disable_tools: list[str] | None = None) -> None:
        async with cls._lock:
            await cls._load_modules(disable_tools)

    @classmethod
    async def _load_modules(cls, disable_tools: list[str] | None = None) -> None:
        disable_tools = disable_tools or []
        cls._disabled_tools.update(disable_tools)

        if cls._registry:
            if disable_tools:
                cls.disable_tools(disable_tools)
            return

        tools_dir = Path(__file__).parent
        if not tools_dir.exists():
            logger.warning("工具目录不存在，无法加载工具。", "zhipu_toolkit.tools")
            return

        for module_info in pkgutil.iter_modules([tools_dir]):
            module_name = module_info.name
            if module_name in ("registry", "__init__", "AbstractTool"):
                continue  # 跳过非工具模块
            try:
                module = importlib.import_module(
                    f".{module_name}", package=__package__
                )
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
        cls._registry[instance.name] = ToolDescriptor(instance=instance)

    @classmethod
    def disable_tools(cls, tools: list[str]) -> None:
        cls._disabled_tools.update(tools)
        # 移除已注册的禁用工具
        for tool_name in tools:
            if tool_name in cls._registry:
                del cls._registry[tool_name]
                logger.info(f"已禁用工具 {tool_name}", "zhipu_toolkit.tools")

    @classmethod
    def get_tool(cls, name: str) -> ToolDescriptor | None:
        return cls._registry.get(name)

    @classmethod
    def get_tools(cls) -> list[ToolDescriptor]:
        return list(cls._registry.values())

    @classmethod
    def clear(cls) -> None:
        cls._registry.clear()

    @classmethod
    async def reload(cls) -> None:
        async with cls._lock:
            cls.clear()
            await cls._load_modules()


def register_tool(tool_cls: type[AbstractTool]) -> type[AbstractTool]:
    ToolRegistry.register(tool_cls)
    return tool_cls


registry = ToolRegistry()
