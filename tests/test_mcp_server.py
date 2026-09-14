from __future__ import annotations

import asyncio

from mcp_server.gateway import MCPGateway
from mcp_server.server import create_server
from mcp_server.tools.music import MusicTools
from music_backend.repository import MusicRepository
from music_backend.service import MusicService
from tests.conftest import FakePlayer


def test_real_mcp_server_publishes_tools(repository: MusicRepository) -> None:
    server = create_server(MusicTools(MusicService(repository, FakePlayer())))
    schemas = asyncio.run(server.list_tools())
    names = {schema.name for schema in schemas}
    assert {
        "search_track", "search_artist", "play_track", "play_artist", "play_random",
        "pause_music", "resume_music", "next_track", "previous_track", "set_volume",
        "get_current_track",
    } <= names
    play_track = next(schema for schema in schemas if schema.name == "play_track")
    assert play_track.inputSchema["required"] == ["title"]


def test_application_gateway_dispatches_through_fastmcp(repository: MusicRepository, tracks) -> None:
    repository.upsert(tracks[0])
    gateway = MCPGateway(MusicTools(MusicService(repository, FakePlayer())))
    result = gateway.call("search_artist", {"artist": "Кино"})
    assert result == {"success": True, "artists": ["Кино"]}
