from __future__ import annotations

from .base import LLM, ToolCall


class LocalLLM(LLM):
    """Extension point for the local model selected in the next project stage."""

    def chat(self, message: str) -> ToolCall | str:
        raise NotImplementedError("Конкретная локальная LLM ещё не выбрана; используйте --mock")
