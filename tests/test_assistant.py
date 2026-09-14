from __future__ import annotations

from core.assistant import Assistant
from llm.base import ToolCall
from llm.mock import MockLLM
from mcp_server.tools.music import MusicTools, ToolGateway
from music_backend.repository import MusicRepository
from music_backend.service import MusicService
from tests.conftest import FakePlayer


def test_mock_pipeline_resolves_artist(repository: MusicRepository, tracks) -> None:
    for track in tracks:
        repository.upsert(track)
    gateway = ToolGateway(MusicTools(MusicService(repository, FakePlayer())))
    reply = Assistant(MockLLM(gateway), gateway).handle("Включи Кино")
    assert reply.tool_call and reply.tool_call.name == "play_artist"
    assert "Кино" in reply.text


def test_mock_pipeline_resolves_track(repository: MusicRepository, tracks) -> None:
    for track in tracks:
        repository.upsert(track)
    gateway = ToolGateway(MusicTools(MusicService(repository, FakePlayer())))
    reply = Assistant(MockLLM(gateway), gateway).handle("Поставь Группу крови")
    assert reply.tool_call and reply.tool_call.name == "play_track"
    assert "Группа крови" in reply.text


def test_mock_pipeline_understands_natural_artist_request(repository: MusicRepository, tracks) -> None:
    for track in tracks:
        repository.upsert(track)
    gateway = ToolGateway(MusicTools(MusicService(repository, FakePlayer())))
    reply = Assistant(MockLLM(gateway), gateway).handle("Давай что-нибудь из Кино")
    assert reply.tool_call == ToolCall("play_artist", {"artist": "Кино"})
    assert reply.tool_result and reply.tool_result["success"] is True
