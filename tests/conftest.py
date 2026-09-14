from __future__ import annotations

from pathlib import Path

import pytest

from music_backend.database import Database
from music_backend.models import Track
from music_backend.repository import MusicRepository
from player.base import AudioPlayer


class FakePlayer(AudioPlayer):
    def __init__(self) -> None:
        self.queue: list[Track] = []
        self.index = -1
        self.paused = False
        self.volume = 70

    def play(self, tracks: list[Track], start_index: int = 0) -> Track:
        self.queue, self.index, self.paused = list(tracks), start_index, False
        return self.queue[self.index]

    def _current(self) -> Track:
        if self.index < 0:
            from player.local_player import PlayerError
            raise PlayerError("Nothing is playing")
        return self.queue[self.index]

    def pause(self) -> None:
        self._current()
        self.paused = True

    def resume(self) -> None:
        self._current()
        self.paused = False

    def stop(self) -> None:
        self.queue, self.index = [], -1

    def next(self) -> Track:
        self._current()
        self.index = (self.index + 1) % len(self.queue)
        return self._current()

    def previous(self) -> Track:
        self._current()
        self.index = (self.index - 1) % len(self.queue)
        return self._current()

    def set_volume(self, volume: int) -> int:
        if not 0 <= volume <= 100:
            raise ValueError
        self.volume = volume
        return volume

    def get_current_track(self) -> Track | None:
        return self.queue[self.index] if self.index >= 0 else None


@pytest.fixture
def repository(tmp_path: Path) -> MusicRepository:
    database = Database(tmp_path / "music.db")
    database.initialize()
    return MusicRepository(database)


@pytest.fixture
def tracks(tmp_path: Path) -> list[Track]:
    return [
        Track("Группа крови", "Кино", tmp_path / "group.mp3", "Группа крови", 275.0),
        Track("Перемен", "Кино", tmp_path / "changes.mp3", "Последний герой", 295.0),
        Track("Yesterday", "The Beatles", tmp_path / "yesterday.mp3", "Help!", 125.0),
    ]
