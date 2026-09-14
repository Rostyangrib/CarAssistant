from __future__ import annotations

from llm.base import LLM, ToolCall
from llm.ollama import OllamaModelNotFoundError, OllamaUnavailableError
from mcp_server.tools.music import MusicTools, ToolGateway
from music_backend.repository import MusicRepository
from music_backend.service import MusicService
from core.assistant import Assistant
from core.command_router import RouteType
from tests.conftest import FakePlayer


class CountingLLM(LLM):
    def __init__(self, result: ToolCall | str = "Ответ") -> None:
        self.calls = 0
        self.result = result
        self.model = "qwen3:4b"

    def chat(self, message: str) -> ToolCall | str:
        self.calls += 1
        return self.result


class FailingLLM(CountingLLM):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    def chat(self, message: str) -> ToolCall | str:
        raise self.error


def _assistant(repository: MusicRepository, llm: LLM) -> tuple[Assistant, FakePlayer]:
    player = FakePlayer()
    service = MusicService(repository, player)
    gateway = ToolGateway(MusicTools(service))
    return Assistant(llm, gateway), player


def test_direct_command_bypasses_llm(repository: MusicRepository, tracks) -> None:
    repository.upsert(tracks[0])
    llm = CountingLLM()
    assistant, player = _assistant(repository, llm)
    player.play([tracks[0]])
    reply = assistant.handle("Пауза")
    assert reply.route is RouteType.DIRECT
    assert reply.text == "Пауза."
    assert reply.direct_latency is not None
    assert reply.llm_latency is None
    assert llm.calls == 0


def test_play_music_uses_direct_random_track(repository: MusicRepository, tracks) -> None:
    repository.upsert(tracks[0])
    llm = CountingLLM()
    assistant, player = _assistant(repository, llm)
    reply = assistant.handle("Включи музыку")
    assert reply.route is RouteType.DIRECT
    assert reply.tool_call and reply.tool_call.name == "play_random"
    assert reply.tool_result and reply.tool_result["success"] is True
    current = player.get_current_track()
    assert current and (current.title, current.artist) == (tracks[0].title, tracks[0].artist)
    assert llm.calls == 0


def test_natural_command_uses_llm_and_mcp(repository: MusicRepository, tracks) -> None:
    repository.upsert(tracks[0])
    llm = CountingLLM(ToolCall("play_artist", {"artist": "Кино"}))
    assistant, _ = _assistant(repository, llm)
    reply = assistant.handle("Давай что-нибудь из Кино")
    assert reply.route is RouteType.LLM
    assert reply.tool_result and reply.tool_result["success"] is True
    assert reply.llm_latency is not None
    assert llm.calls == 1


def test_ollama_errors_are_user_friendly(repository: MusicRepository) -> None:
    unavailable, _ = _assistant(repository, FailingLLM(OllamaUnavailableError()))
    missing, _ = _assistant(repository, FailingLLM(OllamaModelNotFoundError()))
    assert "Ollama" in unavailable.handle("Естественная команда").text
    assert "ollama pull qwen3:4b" in missing.handle("Естественная команда").text
