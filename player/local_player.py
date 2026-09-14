from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from queue import Empty, Queue
from threading import Event, RLock, Thread
from typing import Any

from music_backend.models import Track
from .base import AudioPlayer


logger = logging.getLogger(__name__)


class PlayerError(RuntimeError):
    pass


@dataclass(slots=True)
class _PlayerCommand:
    action: str
    arguments: tuple[object, ...] = ()
    completed: Event = field(default_factory=Event)
    result: Any = None
    error: Exception | None = None


class WindowsMediaPlayer(AudioPlayer):
    """Windows Media Player hosted in a COM message-pumping worker thread."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise PlayerError("WindowsMediaPlayer is available only on Windows")
        self._queue: list[Track] = []
        self._index = -1
        self._volume = 70
        self._lock = RLock()
        self._commands: Queue[_PlayerCommand] = Queue()
        self._ready = Event()
        self._startup_error: Exception | None = None
        self._closed = False
        self._thread = Thread(target=self._worker, name="car-assistant-player", daemon=True)
        self._thread.start()
        if not self._ready.wait(10):
            raise PlayerError("Windows Media Player startup timed out")
        if self._startup_error is not None:
            raise PlayerError("Windows Media Player is unavailable") from self._startup_error

    def _worker(self) -> None:
        try:
            import pythoncom  # type: ignore[import-not-found]
            import win32com.client  # type: ignore[import-not-found]

            pythoncom.CoInitialize()
            player = win32com.client.Dispatch("WMPlayer.OCX")
            player.settings.volume = self._volume
        except Exception as error:
            self._startup_error = error
            self._ready.set()
            return

        self._ready.set()
        running = True
        try:
            while running:
                try:
                    command = self._commands.get(timeout=0.02)
                except Empty:
                    pythoncom.PumpWaitingMessages()
                    continue
                try:
                    if command.action == "play":
                        player.URL = str(command.arguments[0])
                        player.controls.play()
                    elif command.action == "pause":
                        player.controls.pause()
                    elif command.action == "resume":
                        player.controls.play()
                    elif command.action == "stop":
                        player.controls.stop()
                    elif command.action == "volume":
                        player.settings.volume = int(command.arguments[0])
                    elif command.action == "state":
                        command.result = int(player.playState)
                    elif command.action == "errors":
                        command.result = int(player.error.errorCount)
                    elif command.action == "close":
                        player.controls.stop()
                        running = False
                    else:
                        raise PlayerError(f"Unknown player command: {command.action}")
                except Exception as error:
                    command.error = error
                finally:
                    command.completed.set()
                    pythoncom.PumpWaitingMessages()
        finally:
            pythoncom.CoUninitialize()

    def _invoke(self, action: str, *arguments: object) -> Any:
        if self._closed:
            raise PlayerError("Audio player is closed")
        command = _PlayerCommand(action, arguments)
        self._commands.put(command)
        if not command.completed.wait(10):
            raise PlayerError(f"Player command timed out: {action}")
        if command.error is not None:
            raise PlayerError(f"Player command failed: {action}") from command.error
        return command.result

    def _play_current(self) -> Track:
        track = self._queue[self._index]
        self._invoke("play", str(track.path))
        logger.debug("Player action: play %s", track.path)
        return track

    def play(self, tracks: list[Track], start_index: int = 0) -> Track:
        if not tracks:
            raise PlayerError("Playback queue is empty")
        if not 0 <= start_index < len(tracks):
            raise PlayerError("Invalid queue index")
        missing = [track.path for track in tracks if not track.path.is_file()]
        if missing:
            raise PlayerError(f"Audio file not found: {missing[0]}")
        with self._lock:
            self._queue, self._index = list(tracks), start_index
            return self._play_current()

    def _require_current(self) -> Track:
        track = self.get_current_track()
        if track is None:
            raise PlayerError("Nothing is playing")
        return track

    def pause(self) -> None:
        with self._lock:
            self._require_current()
            self._invoke("pause")
            logger.debug("Player action: pause")

    def resume(self) -> None:
        with self._lock:
            self._require_current()
            self._invoke("resume")
            logger.debug("Player action: resume")

    def stop(self) -> None:
        with self._lock:
            if not self._closed:
                self._invoke("stop")
            self._queue, self._index = [], -1

    def next(self) -> Track:
        with self._lock:
            self._require_current()
            self._index = (self._index + 1) % len(self._queue)
            return self._play_current()

    def previous(self) -> Track:
        with self._lock:
            self._require_current()
            self._index = (self._index - 1) % len(self._queue)
            return self._play_current()

    def set_volume(self, volume: int) -> int:
        if not 0 <= volume <= 100:
            raise ValueError("Volume must be between 0 and 100")
        with self._lock:
            self._invoke("volume", volume)
            self._volume = volume
        return volume

    def get_current_track(self) -> Track | None:
        return self._queue[self._index] if self._index >= 0 else None

    def get_playback_state(self) -> int:
        return int(self._invoke("state"))

    def get_error_count(self) -> int:
        return int(self._invoke("errors"))

    @property
    def volume(self) -> int:
        return self._volume

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._invoke("close")
        finally:
            self._closed = True
            self._thread.join(timeout=2)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


# Compatibility name for code created during Stage 1.
WindowsMCIPlayer = WindowsMediaPlayer
