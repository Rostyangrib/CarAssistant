from __future__ import annotations

from abc import ABC, abstractmethod

from music_backend.models import Track


class AudioPlayer(ABC):
    @abstractmethod
    def play(self, tracks: list[Track], start_index: int = 0) -> Track: ...

    @abstractmethod
    def pause(self) -> None: ...

    @abstractmethod
    def resume(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def next(self) -> Track: ...

    @abstractmethod
    def previous(self) -> Track: ...

    @abstractmethod
    def set_volume(self, volume: int) -> int: ...

    @abstractmethod
    def get_current_track(self) -> Track | None: ...
