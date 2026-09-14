from __future__ import annotations

import re

from mcp_server.tools.music import ToolClient
from .base import LLM, ToolCall


class MockLLM(LLM):
    """Deterministic Russian command planner for testing without a local model."""

    def __init__(self, gateway: ToolClient) -> None:
        self.gateway = gateway

    def chat(self, message: str) -> ToolCall | str:
        text = " ".join(message.strip().split())
        normalized = text.casefold()
        if normalized in {"пауза", "поставь на паузу", "приостанови"}:
            return ToolCall("pause_music")
        if normalized in {"продолжи", "продолжить", "возобнови"}:
            return ToolCall("resume_music")
        if normalized in {"следующий", "следующая", "дальше"}:
            return ToolCall("next_track")
        if normalized in {"предыдущий", "предыдущая", "назад"}:
            return ToolCall("previous_track")
        if normalized in {"громче", "сделай громче"}:
            return ToolCall("change_volume", {"delta": 10})
        if normalized in {"тише", "сделай тише"}:
            return ToolCall("change_volume", {"delta": -10})
        if "что сейчас играет" in normalized or normalized == "что играет?":
            return ToolCall("get_current_track")
        volume = re.search(r"(?:громкость|звук)(?:\s+на|\s*=)?\s*(\d{1,3})", normalized)
        if volume:
            return ToolCall("set_volume", {"volume": int(volume.group(1))})
        if "случайн" in normalized and any(word in normalized for word in ("включ", "постав", "давай")):
            return ToolCall("play_random")
        artist_request = re.match(
            r"^(?:давай\s+что-нибудь\s+из|я\s+хочу\s+послушать|найди\s+песни)\s+(.+?)\s*[.!?]*$",
            text,
            re.IGNORECASE,
        )
        if artist_request:
            artist = artist_request.group(1).strip()
            if normalized.startswith("найди песни"):
                return ToolCall("search_artist", {"artist": artist})
            return ToolCall("play_artist", {"artist": artist})
        play = re.match(r"^(?:включи|поставь|давай)(?:\s+песни?|\s+музыку)?\s+(.+?)\s*[.!?]*$", text, re.IGNORECASE)
        if play:
            query = play.group(1).strip()
            artists = self.gateway.call("search_artist", {"artist": query}).get("artists", [])
            if any(str(artist).casefold() == query.casefold() for artist in artists):
                return ToolCall("play_artist", {"artist": query})
            return ToolCall("play_track", {"title": query})
        return "Я пока умею управлять локальной музыкой. Напишите «help», чтобы увидеть команды."
