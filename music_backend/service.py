from __future__ import annotations

import logging

from player.base import AudioPlayer
from .models import Track
from .repository import MusicRepository


logger = logging.getLogger(__name__)


class MusicNotFoundError(LookupError):
    pass


class MusicService:
    def __init__(self, repository: MusicRepository, player: AudioPlayer) -> None:
        self.repository = repository
        self.player = player
        self._volume = 70

    def play_track(self, title: str) -> Track:
        track = self.repository.find_track(title)
        if track is None:
            raise MusicNotFoundError("track")
        logger.debug("MusicService action: play_track %s", title)
        return self.player.play([track])

    def play_artist(self, artist: str) -> Track:
        tracks = self.repository.find_by_artist(artist)
        if not tracks:
            raise MusicNotFoundError("artist")
        logger.debug("MusicService action: play_artist %s", artist)
        return self.player.play(tracks)

    def play_random(self) -> Track:
        track = self.repository.get_random_track()
        if track is None:
            raise MusicNotFoundError("track")
        logger.debug("MusicService action: play_random")
        return self.player.play([track])

    def pause(self) -> None:
        self.player.pause()

    def resume(self) -> None:
        self.player.resume()

    def next(self) -> Track:
        return self.player.next()

    def previous(self) -> Track:
        return self.player.previous()

    def set_volume(self, volume: int) -> int:
        self._volume = self.player.set_volume(volume)
        return self._volume

    def change_volume(self, delta: int) -> int:
        return self.set_volume(max(0, min(100, self._volume + delta)))

    def get_current_track(self) -> Track | None:
        return self.player.get_current_track()
