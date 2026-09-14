from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from llm.base import ToolCall


class RouteType(str, Enum):
    DIRECT = "direct"
    LLM = "llm"


@dataclass(frozen=True, slots=True)
class Route:
    kind: RouteType
    tool_call: ToolCall | None = None


class CommandRouter:
    """Routes only obvious, latency-sensitive commands without an LLM call."""

    _DIRECT = {
        "пауза": ToolCall("pause_music"),
        "стоп": ToolCall("pause_music"),
        "поставь на паузу": ToolCall("pause_music"),
        "останови музыку": ToolCall("pause_music"),
        "продолжи": ToolCall("resume_music"),
        "возобнови": ToolCall("resume_music"),
        "продолжи музыку": ToolCall("resume_music"),
        "следующий": ToolCall("next_track"),
        "следующая": ToolCall("next_track"),
        "следующий трек": ToolCall("next_track"),
        "следующая песня": ToolCall("next_track"),
        "включи следующий": ToolCall("next_track"),
        "предыдущий": ToolCall("previous_track"),
        "предыдущий трек": ToolCall("previous_track"),
        "включи предыдущий": ToolCall("previous_track"),
        "громче": ToolCall("change_volume", {"delta": 10}),
        "сделай громче": ToolCall("change_volume", {"delta": 10}),
        "тише": ToolCall("change_volume", {"delta": -10}),
        "сделай тише": ToolCall("change_volume", {"delta": -10}),
        "включи музыку": ToolCall("play_random"),
        "включи любую музыку": ToolCall("play_random"),
        "включи музыку любую": ToolCall("play_random"),
        "поставь музыку": ToolCall("play_random"),
        "поставь случайный трек": ToolCall("play_random"),
        "включи случайную музыку": ToolCall("play_random"),
    }

    def route(self, message: str) -> Route:
        normalized = re.sub(r"[.!?]+$", "", " ".join(message.casefold().split())).strip()
        tool_call = self._DIRECT.get(normalized)
        if tool_call is None:
            artist_match = re.fullmatch(
                r"(?:(?:включи|ключи)\s+(?:исполнителя?|исполнитель)|"
                r"(?:исполнитель|респонитель))\s+(?:на\s+)?(.+)",
                normalized,
            )
            if artist_match:
                tool_call = ToolCall("play_artist", {"artist": artist_match.group(1).strip()})
        if tool_call is None:
            track_match = re.fullmatch(r"песня\s+(.+)", normalized)
            if track_match:
                tool_call = ToolCall("play_track", {"title": track_match.group(1).strip()})
        return Route(RouteType.DIRECT, tool_call) if tool_call else Route(RouteType.LLM)
