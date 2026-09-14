from __future__ import annotations

from app.config import Settings
from music_backend.database import Database
from music_backend.repository import MusicRepository
from music_backend.service import MusicService
from player.local_player import WindowsMediaPlayer
from .tools.music import MusicTools


def create_server(tools: MusicTools):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as error:
        raise RuntimeError("Install dependencies with: pip install -r requirements.txt") from error

    server = FastMCP("car-ai-assistant")
    server.tool(description="Find local tracks whose title contains the query.")(tools.search_track)
    server.tool(description="Find a local music artist by name.")(tools.search_artist)
    server.tool(description="Play a local track by title.")(tools.play_track)
    server.tool(description="Play the local tracks of an artist.")(tools.play_artist)
    server.tool(description="Play a random local track.")(tools.play_random)
    server.tool(description="Pause the current music.")(tools.pause_music)
    server.tool(description="Resume paused music.")(tools.resume_music)
    server.tool(description="Play the next track in the queue.")(tools.next_track)
    server.tool(description="Play the previous track in the queue.")(tools.previous_track)
    server.tool(description="Set volume from 0 to 100.")(tools.set_volume)
    server.tool(description="Change volume by a signed delta.")(tools.change_volume)
    server.tool(description="Return the current track, if any.")(tools.get_current_track)
    return server


def main() -> None:
    settings = Settings.load()
    database = Database(settings.database_path)
    database.initialize()
    tools = MusicTools(MusicService(MusicRepository(database), WindowsMediaPlayer()))
    create_server(tools).run(transport="stdio")


if __name__ == "__main__":
    main()
