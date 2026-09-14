from __future__ import annotations

import pytest

from music_backend.repository import MusicRepository
from music_backend.service import MusicNotFoundError, MusicService
from tests.conftest import FakePlayer


@pytest.fixture
def service(repository: MusicRepository, tracks) -> tuple[MusicService, FakePlayer]:
    for track in tracks:
        repository.upsert(track)
    player = FakePlayer()
    return MusicService(repository, player), player


def test_play_track_artist_and_random(service) -> None:
    music, player = service
    assert music.play_track("Yesterday").title == "Yesterday"
    assert music.play_artist("Кино").artist == "Кино"
    assert len(player.queue) == 2
    assert music.play_random() is not None


def test_transport_controls(service) -> None:
    music, player = service
    music.play_artist("Кино")
    first = music.get_current_track()
    assert music.next() != first
    assert music.previous() == first
    music.pause()
    assert player.paused
    music.resume()
    assert not player.paused


def test_volume(service) -> None:
    music, player = service
    assert music.set_volume(25) == 25
    assert music.change_volume(10) == 35
    assert music.change_volume(-100) == 0
    assert player.volume == 0


def test_missing_track(service) -> None:
    with pytest.raises(MusicNotFoundError):
        service[0].play_track("Нет такого")
