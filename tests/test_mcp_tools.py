from __future__ import annotations

import pytest

from mcp_server.tools.music import MusicTools, ToolGateway
from music_backend.repository import MusicRepository
from music_backend.service import MusicService
from tests.conftest import FakePlayer


@pytest.fixture
def gateway(repository: MusicRepository, tracks) -> ToolGateway:
    for track in tracks:
        repository.upsert(track)
    return ToolGateway(MusicTools(MusicService(repository, FakePlayer())))


def test_search_tools(gateway: ToolGateway) -> None:
    assert len(gateway.call("search_track", {"query": "Перемен"})["tracks"]) == 1
    assert gateway.call("search_artist", {"artist": "Кино"})["artists"] == ["Кино"]


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("play_track", {"title": "Yesterday"}),
        ("play_artist", {"artist": "Кино"}),
        ("play_random", {}),
    ],
)
def test_play_tools(gateway: ToolGateway, name: str, arguments: dict) -> None:
    assert gateway.call(name, arguments)["success"] is True


def test_all_transport_and_volume_tools(gateway: ToolGateway) -> None:
    gateway.call("play_artist", {"artist": "Кино"})
    for name in ("pause_music", "resume_music", "next_track", "previous_track", "get_current_track"):
        assert gateway.call(name)["success"] is True
    assert gateway.call("set_volume", {"volume": 40})["volume"] == 40
    assert gateway.call("change_volume", {"delta": 10})["volume"] == 50


def test_tool_errors(gateway: ToolGateway) -> None:
    assert gateway.call("play_track", {"title": "Нет"})["error"] == "track_not_found"
    assert gateway.call("play_artist", {"artist": "Нет"})["error"] == "artist_not_found"
    assert gateway.call("missing")["error"] == "unknown_tool"
    assert gateway.call("play_artist", {})["error"] == "invalid_arguments"
