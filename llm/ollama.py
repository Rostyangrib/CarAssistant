from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from .base import LLM, ToolCall


logger = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    """Base error for a user-recoverable local Ollama failure."""


class OllamaUnavailableError(OllamaError):
    pass


class OllamaModelNotFoundError(OllamaError):
    pass


class OllamaInvalidResponseError(OllamaError):
    pass


TOOL_SCHEMAS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "search_track", "description": "Только найти треки без воспроизведения. Использовать при явных словах «найди», «покажи» или «есть ли».",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_artist", "description": "Только найти исполнителя без воспроизведения. Использовать при явных словах «найди», «покажи» или «есть ли».",
            "parameters": {"type": "object", "properties": {"artist": {"type": "string"}}, "required": ["artist"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_track", "description": "Воспроизвести трек по названию. Использовать также, когда пользователь написал только название трека.",
            "parameters": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_artist", "description": "Воспроизвести музыку исполнителя. Использовать также, когда пользователь написал только имя исполнителя.",
            "parameters": {"type": "object", "properties": {"artist": {"type": "string"}}, "required": ["artist"]},
        },
    },
    {"type": "function", "function": {"name": "play_random", "description": "Воспроизвести случайный трек.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "pause_music", "description": "Поставить музыку на паузу.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "resume_music", "description": "Продолжить воспроизведение.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "next_track", "description": "Перейти к следующему треку.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "previous_track", "description": "Перейти к предыдущему треку.", "parameters": {"type": "object", "properties": {}}}},
    {
        "type": "function",
        "function": {
            "name": "set_volume", "description": "Установить громкость от 0 до 100.",
            "parameters": {"type": "object", "properties": {"volume": {"type": "integer", "minimum": 0, "maximum": 100}}, "required": ["volume"]},
        },
    },
    {"type": "function", "function": {"name": "get_current_track", "description": "Узнать текущий трек.", "parameters": {"type": "object", "properties": {}}}},
]

ALLOWED_TOOLS = {str(schema["function"]["name"]) for schema in TOOL_SCHEMAS}  # type: ignore[index]
Transport = Callable[[dict[str, object]], dict[str, object]]


def _parse_textual_tool_call(content: str) -> ToolCall | None:
    """Accept a narrow fallback used by small models that print a call instead of structuring it."""
    normalized_content = content.replace('<|"|>', '"')
    brace_match = re.fullmatch(
        r"\s*(search_track|search_artist|play_track|play_artist|set_volume)"
        r"\s*\{\s*(query|artist|title|volume)\s*[:=]\s*(.*?)\s*\}\s*",
        normalized_content,
        flags=re.IGNORECASE,
    )
    if brace_match:
        name, argument, value = brace_match.groups()
        expected = {
            "search_track": "query", "search_artist": "artist", "play_track": "title",
            "play_artist": "artist", "set_volume": "volume",
        }
        name = name.casefold()
        if expected[name] != argument.casefold():
            return None
        value = value.strip().strip("\"'")
        parsed_value: object = int(value) if name == "set_volume" and value.isdigit() else value
        return ToolCall(name, {expected[name]: parsed_value})
    match = re.fullmatch(
        r"\s*(search_track|search_artist|play_track|play_artist|set_volume)"
        r"\s+(?:с\s+)?(query|artist|title|volume)\s*=\s*[\"']?(.+?)[\"']?\s*",
        normalized_content,
        flags=re.IGNORECASE,
    )
    if match:
        name, argument, value = match.groups()
        expected = {
            "search_track": "query", "search_artist": "artist", "play_track": "title",
            "play_artist": "artist", "set_volume": "volume",
        }
        name = name.casefold()
        if expected[name] != argument.casefold():
            return None
        parsed_value: object = int(value) if name == "set_volume" and value.isdigit() else value
        return ToolCall(name, {expected[name]: parsed_value})
    simple_match = re.fullmatch(
        r"\s*(play_random|pause_music|resume_music|next_track|previous_track|get_current_track)"
        r"\s*(?:\(\s*\)|\{\s*\})?\s*",
        normalized_content,
        flags=re.IGNORECASE,
    )
    if simple_match:
        return ToolCall(simple_match.group(1).casefold())
    return None


class OllamaLLM(LLM):
    def __init__(
        self,
        host: str,
        model: str,
        timeout: float = 60.0,
        system_prompt_path: Path | None = None,
        transport: Transport | None = None,
    ) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        prompt_path = system_prompt_path or Path(__file__).with_name("system_prompt.txt")
        self.system_prompt = prompt_path.read_text(encoding="utf-8")
        self._transport = transport or self._post

    def _post(self, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            if error.code == 404 or "not found" in body.casefold():
                raise OllamaModelNotFoundError(self.model) from error
            raise OllamaUnavailableError(body or str(error)) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise OllamaUnavailableError(str(error)) from error
        except (json.JSONDecodeError, UnicodeError) as error:
            raise OllamaInvalidResponseError("Ollama returned invalid JSON") from error

    def chat(self, message: str) -> ToolCall | str:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": message},
            ],
            "tools": TOOL_SCHEMAS,
            "stream": False,
            "think": False,
            "options": {"temperature": 0},
        }
        logger.debug("Ollama request: model=%s", self.model)
        response = self._transport(payload)
        try:
            response_message = response["message"]
            if not isinstance(response_message, dict):
                raise TypeError
            tool_calls = response_message.get("tool_calls") or []
            if tool_calls:
                function = tool_calls[0]["function"]
                name = function["name"]
                arguments: Any = function.get("arguments", {})
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                if name not in ALLOWED_TOOLS or not isinstance(arguments, dict):
                    raise ValueError
                return ToolCall(str(name), arguments)
            content = response_message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError
            textual_call = _parse_textual_tool_call(content)
            if textual_call is not None:
                logger.warning("Ollama returned a textual tool call; applying compatibility parser")
                return textual_call
            return content.strip()
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise OllamaInvalidResponseError("Unexpected Ollama response structure") from error
