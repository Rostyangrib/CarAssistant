from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    arguments: dict[str, object] = field(default_factory=dict)


class LLM(ABC):
    @abstractmethod
    def chat(self, message: str) -> ToolCall | str:
        """Return either a tool decision or a direct conversational response."""
