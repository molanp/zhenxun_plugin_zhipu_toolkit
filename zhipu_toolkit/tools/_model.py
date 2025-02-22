from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field


class Tool(BaseModel):
    name: str = Field(default="")
    parameters: dict[str, Any] = Field(default_factory=dict)
    description: str = Field(default="")
    func: Callable | None = None

    def to_dict(self):
        if "type" not in self.parameters:
            self.parameters["type"] = "object"
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
