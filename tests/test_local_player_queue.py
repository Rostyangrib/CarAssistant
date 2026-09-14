from __future__ import annotations

from player.local_player import _load_playlist, _media_path_key


class FakePlaylist:
    def __init__(self) -> None:
        self.media = []

    def appendItem(self, media) -> None:
        self.media.append(media)

    def item(self, index):
        return self.media[index]


class FakeControls:
    currentItem = None

    def __init__(self) -> None:
        self.played = False

    def play(self) -> None:
        self.played = True


class FakeWMP:
    def __init__(self) -> None:
        self.controls = FakeControls()
        self.currentPlaylist = None

    def newPlaylist(self, _name, _url):
        return FakePlaylist()

    def newMedia(self, path):
        return f"media:{path}"


def test_player_builds_native_playlist_for_automatic_advancement() -> None:
    player = FakeWMP()
    _load_playlist(player, ("first.mp3", "second.mp3"), 0)
    assert player.currentPlaylist.media == ["media:first.mp3", "media:second.mp3"]
    assert player.controls.currentItem == "media:first.mp3"
    assert player.controls.played is True


def test_media_url_matches_windows_path() -> None:
    assert _media_path_key("file:///C:/Music/song.mp3") == _media_path_key("C:/Music/song.mp3")
