from __future__ import annotations

import argparse

from cli.interface import CLI
from core.assistant import Assistant
from llm.mock import MockLLM
from llm.ollama import OllamaLLM
from mcp_server.gateway import MCPGateway
from mcp_server.tools.music import MusicTools
from music_backend.database import Database
from music_backend.repository import MusicRepository
from music_backend.scanner import MusicScanner
from music_backend.service import MusicService
from player.local_player import WindowsMediaPlayer
from .config import Settings
from .logging_config import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local text car assistant")
    parser.add_argument("--scan", action="store_true", help="scan the local MP3 library and exit")
    parser.add_argument("--debug", action="store_true", help="show tool decisions and detailed logs")
    parser.add_argument("--mock", action="store_true", help="use deterministic mock LLM instead of Ollama")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = Settings.load()
    configure_logging(args.debug, settings.log_level)
    database = Database(settings.database_path)
    database.initialize()
    repository = MusicRepository(database)
    if args.scan:
        print("Scanning music library...")
        result = MusicScanner(repository).scan(settings.music_dir)
        print(f"Found: {result.found} tracks")
        print(f"Added: {result.added}")
        print(f"Updated: {result.updated}")
        print(f"Removed: {result.removed}")
        return 0
    gateway = MCPGateway(MusicTools(MusicService(repository, WindowsMediaPlayer())))
    llm = (
        MockLLM(gateway)
        if args.mock
        else OllamaLLM(settings.ollama_host, settings.ollama_model, settings.ollama_timeout)
    )
    CLI(Assistant(llm, gateway), debug=args.debug).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
