from __future__ import annotations

import logging
from typing import Any, Callable, Protocol

from music_backend.service import MusicNotFoundError, MusicService
from player.local_player import PlayerError


logger = logging.getLogger(__name__)


class MusicTools:
    def __init__(self, service: MusicService) -> None:
        self.service = service

    @staticmethod
    def _track(track: Any) -> dict[str, object]:
        return {"success": True, "track": track.as_dict()}

    def search_track(self, query: str) -> dict[str, object]:
        tracks = self.service.repository.find_tracks(query)
        return {"success": True, "tracks": [track.as_dict() for track in tracks]}

    def search_artist(self, artist: str) -> dict[str, object]:
        resolved = self.service.repository.find_artist(artist)
        return {"success": True, "artists": [resolved] if resolved else []}

    def play_track(self, title: str) -> dict[str, object]:
        return self._run(lambda: self._track(self.service.play_track(title)))

    def play_artist(self, artist: str) -> dict[str, object]:
        return self._run(lambda: self._track(self.service.play_artist(artist)))

    def play_random(self) -> dict[str, object]:
        return self._run(lambda: self._track(self.service.play_random()))

    def pause_music(self) -> dict[str, object]:
        return self._run(lambda: self._simple(self.service.pause()))

    def resume_music(self) -> dict[str, object]:
        return self._run(lambda: self._simple(self.service.resume()))

    def next_track(self) -> dict[str, object]:
        return self._run(lambda: self._track(self.service.next()))

    def previous_track(self) -> dict[str, object]:
        return self._run(lambda: self._track(self.service.previous()))

    def set_volume(self, volume: int) -> dict[str, object]:
        return self._run(lambda: {"success": True, "volume": self.service.set_volume(volume)})

    def change_volume(self, delta: int) -> dict[str, object]:
        return self._run(lambda: {"success": True, "volume": self.service.change_volume(delta)})

    def get_current_track(self) -> dict[str, object]:
        track = self.service.get_current_track()
        return {"success": True, "track": track.as_dict() if track else None}

    @staticmethod
    def _simple(_: object = None) -> dict[str, object]:
        return {"success": True}

    @staticmethod
    def _run(action: Callable[[], dict[str, object]]) -> dict[str, object]:
        try:
            return action()
        except MusicNotFoundError as error:
            return {"success": False, "error": f"{error.args[0]}_not_found"}
        except (PlayerError, ValueError) as error:
            logger.exception("Music tool failed")
            return {"success": False, "error": "player_error", "detail": str(error)}
        except Exception as error:
            logger.exception("Unexpected music tool error")
            return {"success": False, "error": "internal_error", "detail": str(error)}


class ToolGateway:
    """In-process MCP tool adapter used by tests and the mock planner."""

    def __init__(self, tools: MusicTools) -> None:
        self.tools = tools
        self._handlers: dict[str, Callable[..., dict[str, object]]] = {
            name: getattr(tools, name)
            for name in (
                "search_track", "search_artist", "play_track", "play_artist", "play_random",
                "pause_music", "resume_music", "next_track", "previous_track", "set_volume",
                "change_volume", "get_current_track",
            )
        }

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, object]:
        logger.debug("Selected tool: %s; arguments=%s", name, arguments or {})
        handler = self._handlers.get(name)
        if handler is None:
            return {"success": False, "error": "unknown_tool"}
        try:
            result = handler(**(arguments or {}))
        except (TypeError, ValueError) as error:
            logger.exception("Invalid tool arguments for %s", name)
            return {"success": False, "error": "invalid_arguments", "detail": str(error)}
        logger.debug("Tool result: %s", result)
        return result


class ToolClient(Protocol):
    tools: MusicTools

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, object]: ...
