from __future__ import annotations

from pathlib import Path

from music_backend.repository import MusicRepository
from music_backend.scanner import MusicScanner


def _frame(name: str, text: str) -> bytes:
    payload = b"\x03" + text.encode("utf-8")
    return name.encode("ascii") + len(payload).to_bytes(4, "big") + b"\x00\x00" + payload


def _synchsafe(number: int) -> bytes:
    return bytes(((number >> 21) & 0x7F, (number >> 14) & 0x7F, (number >> 7) & 0x7F, number & 0x7F))


def _write_tag(path: Path, title: str, artist: str, album: str) -> None:
    body = _frame("TIT2", title) + _frame("TPE1", artist) + _frame("TALB", album)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ID3\x03\x00\x00" + _synchsafe(len(body)) + body)


def test_scanner_finds_metadata_and_avoids_duplicates(tmp_path: Path, repository: MusicRepository) -> None:
    music = tmp_path / "library"
    _write_tag(music / "wrong artist" / "wrong title.MP3", "Перемен", "Кино", "Последний герой")
    (music / "ignore.txt").write_text("not music")
    scanner = MusicScanner(repository)
    first = scanner.scan(music)
    second = scanner.scan(music)
    track = repository.find_track("Перемен")
    assert (first.found, first.added, first.updated) == (1, 1, 0)
    assert (second.found, second.added, second.updated) == (1, 0, 0)
    assert track and (track.artist, track.album) == ("Кино", "Последний герой")


def test_scanner_updates_and_removes(tmp_path: Path, repository: MusicRepository) -> None:
    music = tmp_path / "library"
    path = music / "Кино" / "track.mp3"
    _write_tag(path, "Старая", "Кино", "")
    scanner = MusicScanner(repository)
    scanner.scan(music)
    _write_tag(path, "Новая", "Кино", "")
    assert scanner.scan(music).updated == 1
    path.unlink()
    assert scanner.scan(music).removed == 1
    assert repository.find_track("Новая") is None
